from concurrent.futures import ThreadPoolExecutor, as_completed
from django.apps import apps
import threading

from .audio_chunker import chunk_audio
from .transcriber import transcribe_chunk
from .cancel import get_cancel_event
from .interview_intelligence import build_segments
from .regex_normalizer import normalize_text
from ..services.segment_deduplicator import deduplicate_segments

import logging
import time

# Number of audio chunks that can be transcribed simultaneously.
MAX_TRANSCRIBE_WORKERS = 1

logger = logging.getLogger("transcription")


def _mark_cancelled(transcription) -> None:
    """
    Mark a transcription as cancelled.
    """
    transcription.status = "CANCELLED"

    transcription.save(
        update_fields=["status"]
    )


def _update_progress(
    transcription,
    all_segments: list[dict],
    completed_chunks: int,
    total_chunks: int,
) -> None:
    """
    Persist partial transcript results and progress.

    Saving after each completed chunk means completed work is not
    lost if the worker crashes later in the transcription.
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


def _transcribe_single_chunk(
    index: int,
    chunk: dict,
    fast_mode: bool,
) -> tuple[int, list[dict]]:
    """
    Transcribe one chunk.

    The index is returned so the caller can associate the result
    with the original chunk even though futures may finish in
    a different order.
    """
    start_time = time.perf_counter()
    thread_name = threading.current_thread().name
    
    logger.info(
        "START chunk %d | thread=%s | audio_start=%.2fs | duration=%.2fs",
        index,
        thread_name,
        chunk["start"],
        chunk["duration"]
    )
    try:
        raw_segments = transcribe_chunk(
            chunk["path"],
            fast_mode=fast_mode,
        )

        structured_segments = build_segments(
            raw_segments,
            normalizer_func=normalize_text,
            offset=chunk["start"],
        )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "FINISH chunk %d | thread=%s | elapsed=%.2fs",
            index,
            thread_name,
            elapsed,
        )

        return index, structured_segments

    except Exception:
        elapsed = time.perf_counter() - start_time

        logger.exception(
            "FAILED chunk %d | thread=%s | elapsed=%.2fs",
            index,
            thread_name,
            elapsed,
        )

        raise


def process_transcription(
    transcription_id: int,
    fast_mode: bool = True,
) -> None:
    """
    Full transcription pipeline.

    Pipeline:

    1. Normalize audio.
    2. Split audio into overlapping chunks.
    3. Transcribe multiple chunks concurrently.
    4. Apply absolute chunk timestamps.
    5. Build structured speaker/question/answer segments.
    6. Normalize Liberian English / Kolokwa.
    7. Deduplicate overlap-generated segments.
    8. Persist progress after each completed chunk.
    """
    Transcription = apps.get_model(
        "transcription",
        "Transcription",
    )

    transcription = None

    try:
        transcription = Transcription.objects.get(
            id=transcription_id
        )

        cancel_event = get_cancel_event(
            transcription_id
        )

        # Check cancellation before doing any work.
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

        # ---------------------------------------------------------
        # Create all audio chunks first.
        #
        # This stage remains sequential. The concurrency below is
        # specifically for Whisper transcription.
        # ---------------------------------------------------------
        chunks = chunk_audio(
            transcription.audio_file.path
        )

        total_chunks = len(chunks)

        if total_chunks == 0:
            raise RuntimeError(
                "No audio chunks were created."
            )

        all_segments: list[dict] = []

        # ---------------------------------------------------------
        # Transcribe chunks concurrently.
        #
        # With MAX_TRANSCRIBE_WORKERS = 2:
        #
        #   chunk 0 ────────────────┐
        #                           ├─ running simultaneously
        #   chunk 1 ────────────────┘
        #
        # Once one finishes, the executor starts the next chunk.
        # ---------------------------------------------------------
        with ThreadPoolExecutor(
            max_workers=MAX_TRANSCRIBE_WORKERS,
            thread_name_prefix="transcription-chunk",
        ) as executor:

            futures = {
                executor.submit(
                    _transcribe_single_chunk,
                    index,
                    chunk,
                    fast_mode,
                ): index
                for index, chunk in enumerate(chunks)
            }

            completed_chunks = 0

            for future in as_completed(futures):
                # -------------------------------------------------
                # Check cancellation before accepting another result.
                # -------------------------------------------------
                if cancel_event.is_set():
                    logger.info(
                        "Transcription %s cancelled while "
                        "chunks were running.",
                        transcription_id,
                    )

                    # Cancel futures that have not started yet.
                    for pending_future in futures:
                        pending_future.cancel()

                    _mark_cancelled(transcription)
                    return

                try:
                    index, structured_segments = (
                        future.result()
                    )

                except Exception:
                    # Cancel work that has not started.
                    for pending_future in futures:
                        if pending_future is not future:
                            pending_future.cancel()

                    raise

                # -------------------------------------------------
                # Add the completed chunk's segments.
                #
                # We do NOT assume chunks finish in order.
                # Chunk 1 may finish before chunk 0.
                # -------------------------------------------------
                all_segments.extend(
                    structured_segments
                )

                # -------------------------------------------------
                # Remove duplicates caused by the 2-second overlap.
                # -------------------------------------------------
                all_segments = deduplicate_segments(
                    all_segments
                )

                completed_chunks += 1

                _update_progress(
                    transcription=transcription,
                    all_segments=all_segments,
                    completed_chunks=completed_chunks,
                    total_chunks=total_chunks,
                )

                logger.info(
                    "Transcription %s: completed chunk %d/%d",
                    transcription_id,
                    completed_chunks,
                    total_chunks,
                )

        # ---------------------------------------------------------
        # Final cancellation check.
        # ---------------------------------------------------------
        if cancel_event.is_set():
            _mark_cancelled(transcription)
            return

        # ---------------------------------------------------------
        # Final ordering.
        #
        # Because futures complete in arbitrary order, the segments
        # must be sorted by their absolute timestamps before the
        # transcript is finalized.
        # ---------------------------------------------------------
        all_segments.sort(
            key=lambda segment: (
                segment["start"],
                segment["end"],
            )
        )

        # One final deduplication pass after ordering.
        all_segments = deduplicate_segments(
            all_segments
        )

        transcription.structured_segments = all_segments
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

        # Re-raise so Celery/background infrastructure knows
        # that the transcription failed.
        raise