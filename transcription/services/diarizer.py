from pyannote.audio import Pipeline
import os

# Lazy-loaded global pipeline
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization",
            use_auth_token=True  # add if required for huggingface
        )
    return _pipeline


def diarize_audio(file_path, chunk_length=600, overlap=2):
    """
    Diarize audio in chunks and merge segments with adjusted timestamps.
    Args:
        file_path: full audio file path
        chunk_length: chunk size in seconds
        overlap: overlap in seconds between chunks
    Returns:
        List of dicts: [{"start": float, "end": float, "speaker": str}, ...]
    """
    duration = float(os.popen(
        f"ffprobe -v error -show_entries format=duration "
        f"-of default=noprint_wrappers=1:nokey=1 \"{file_path}\""
    ).read().strip())

    if duration <= chunk_length:
        # Short audio: process directly
        pipeline = get_pipeline()
        diarization = pipeline(file_path)
        return [
            {"start": s.start, "end": s.end, "speaker": s.label}
            for s in diarization.itertracks(yield_label=True)
        ]

    # Long audio: process in chunks
    segments = []
    pipeline = get_pipeline()
    total_chunks = int((duration + chunk_length - 1) // chunk_length)

    for i in range(total_chunks):
        start = max(0, i * chunk_length - overlap)
        end = min(duration, (i + 1) * chunk_length + overlap)

        chunk_file = f"{file_path}_diarize_chunk_{i}.wav"
        os.system(
            f'ffmpeg -y -i "{file_path}" -ss {start} -to {end} "{chunk_file}" -loglevel quiet'
        )

        diarization = pipeline(chunk_file)
        for s in diarization.itertracks(yield_label=True):
            seg_start = s.start + start
            seg_end = s.end + start
            segments.append({"start": seg_start, "end": seg_end, "speaker": s.label})

        # Clean up chunk file
        os.remove(chunk_file)

    # Optional: merge consecutive segments with same speaker
    merged = []
    for seg in segments:
        if not merged:
            merged.append(seg)
            continue
        last = merged[-1]
        if last["speaker"] == seg["speaker"] and seg["start"] <= last["end"]:
            last["end"] = max(last["end"], seg["end"])
        else:
            merged.append(seg)

    return merged