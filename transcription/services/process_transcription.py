from concurrent.futures import ThreadPoolExecutor
from django.apps import apps
from .audio_chunker import chunk_audio
from .transcriber import transcribe_chunk
from .cancel import get_cancel_event
from .interview_intelligence import build_segments
from .regex_normalizer import normalize_text

CHUNK_SECONDS = 600
MAX_TRANSCRIBE_WORKERS = 2


def process_transcription(transcription_id: int, fast_mode=True):
    """
    Full transcription pipeline:
    - Chunk audio
    - Transcribe each chunk with Whisper (English forced)
    - Build structured segments with speaker/type
    - Normalize Kolokwa/Creole to English
    - Save results in Django model
    """
    Transcription = apps.get_model("transcription", "Transcription")
    transcription = Transcription.objects.get(id=transcription_id)

    cancel_event = get_cancel_event(transcription_id)

    # 1️⃣ Chunk audio
    chunks = chunk_audio(transcription.audio_file.path)

    all_segments = []

    # 2️⃣ Transcribe chunks (parallel)
    offset = 0.0
    total_chunks = len(chunks)
    if cancel_event.is_set():
        transcription.status = "CANCELLED"
        transcription.save(update_fields=["status"])
        return
    def _transcribe(chunk_path: str):
        return transcribe_chunk(chunk_path, fast_mode)

    with ThreadPoolExecutor(max_workers=MAX_TRANSCRIBE_WORKERS) as executor:
        raw_segments_list = list(executor.map(_transcribe, chunks))

    # 3️⃣ Build segments per chunk and persist progress
    for idx, raw_segments in enumerate(raw_segments_list):
        if cancel_event.is_set():
            transcription.status = "CANCELLED"
            transcription.save(update_fields=["status"])
            return

        # Build structured segments (with speaker/type) and normalize English
        structured_segments = build_segments(
            raw_segments,
            normalizer_func=normalize_text,
            offset=offset
        )

        all_segments.extend(structured_segments)

        # Increment offset for next chunk
        if raw_segments:
            chunk_duration = max(seg["end"] for seg in raw_segments)
        else:
            chunk_duration = 0
        offset += chunk_duration

        # Save partial progress after each chunk
        transcription.structured_segments = all_segments
        transcription.progress = int(((idx + 1) / total_chunks) * 100) if total_chunks else 100
        transcription.save(update_fields=["structured_segments", "progress"])

    # 4️⃣ Sort by start time
    all_segments.sort(key=lambda x: x["start"])

    # 5️⃣ Save to model
    transcription.structured_segments = all_segments
    transcription.status = "DONE"
    transcription.save(update_fields=["structured_segments", "status"])
