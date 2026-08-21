from concurrent.futures import ThreadPoolExecutor
from django.apps import apps
from .audio_chunker import chunk_audio
from .transcriber import transcribe_chunk
from .cancel import get_cancel_event
from .interview_intelligence import build_segments
from .regex_normalizer import normalize_text
import logging
from ..services.segment_deduplicator import deduplicate_segments

CHUNK_SECONDS = 600
MAX_TRANSCRIBE_WORKERS = 2

logger = logging.getLogger("transcription")

def _mark_cancelled(transcription) -> None:
    """
    mark a transcription as cancelled
    """
    transcription.status = "CANCELLED"

    transcription.save(
        update_fields=[
            "status",
        ]
    )


def _update_progress( transcription, all_segments: list[dict],
    completed_chunks: int,
    total_chunks: int,
) -> None:
    """
    Persist partial transcript results and progress.

    Saving after each chunk protects completed work if
    the worker crashes during a long transcription.
    """
    if total_chunks > 0:
        progress = int(
            (completed_chunks / total_chunks) * 100
        )
    else:
        progress = 100

    transcription.structured_segments = all_segments
    transcription.progress = progress

    transcription.save(
        update_fields=[
            "structured_segments",
            "progress",
        ]
    )

def process_transcription(transcription_id: int, fast_mode=True) -> None:
    """
    Full transcription pipeline:
    
    - Normalize audio
    - Split audion into overlapping chunks.
    - Transcribe each chunk with Whisper (Use English forcibly instead of guessing the language)
    - Apply the chunk's absolute timestamp
    - Build structured segments with speaker/type
    - Normalize Kolokwa/Creole to English
    - Save results in Django model
    """
    Transcription = apps.get_model("transcription", "Transcription")
    
    
    transcription = None

    try:
        transcription = (Transcription.objects.get(id=transcription_id))

        cancel_event = get_cancel_event(transcription_id)

        # Check cancellation before starting.
        if cancel_event.is_set():
            _mark_cancelled(transcription)
            return

        transcription.status = "PROCESSING"
        transcription.progress = 0

        transcription.save(
            update_fields=[
                "status",
                "progress",
            ]
        )

        chunks = chunk_audio(
            transcription.audio_file.path
        )

        total_chunks = len(chunks)

        all_segments: list[dict] = []

        for index, chunk in enumerate(chunks):
            # Stop before starting the next chunk.
            if cancel_event.is_set():
                _mark_cancelled(transcription)
                return

            raw_segments = transcribe_chunk(
                chunk["path"],
                fast_mode=fast_mode,
            )
            
            # Stop before processing the result.
            if cancel_event.is_set():
                _mark_cancelled(transcription)
                return
            
            
            structured_segments = build_segments(
                raw_segments,
                normalizer_func=normalize_text,
                # use the actual audio chunk
                # start instead of estimating it from
                # whisper final segment
                offset=chunk["start"]
            )
            
            all_segments.extend(
                structured_segments
            )

            # Remove duplicates caused by overlap before
            # persisting partial progress.
            all_segments = deduplicate_segments(
                all_segments
            )

            _update_progress(
                transcription=transcription,
                all_segments=all_segments,
                completed_chunks=index + 1,
                total_chunks=total_chunks,
            )

        # Final cancellation check.
        if cancel_event.is_set():
            _mark_cancelled(transcription)
            return

        # Final ordering and duplicate cleanup.
        all_segments.sort(
            key=lambda segment: (
                segment["start"],
                segment["end"],
            )
        )

        all_segments = deduplicate_segments(
            all_segments
        )

        transcription.structured_segments = (
            all_segments
        )

        transcription.progress = 100
        transcription.status = "DONE"

        transcription.save(
            update_fields=[
                "structured_segments",
                "progress",
                "status",
            ]
        )

        logger.info(
            "Transcription %s completed successfully.",
            transcription_id,
        )

    except Exception as exc:
        logger.exception(
            "Transcription failed for ID %s",
            transcription_id,
        )

        if transcription is not None:
            transcription.status = "ERROR"
            transcription.error_message = str(exc)

            transcription.save(
                update_fields=[
                    "status",
                    "error_message",
                ]
            )

        # Re-raise so Celery knows the task failed.
        raise