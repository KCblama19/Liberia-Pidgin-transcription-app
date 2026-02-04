import os
import math
import subprocess

DEFAULT_CHUNK_LENGTH = 600  # seconds
DEFAULT_OVERLAP = 2


def get_audio_duration(audio_path: str) -> float:
    """
    Returns the duration of an audio file in seconds using ffprobe.
    """
    try:
        return float(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                stderr=subprocess.STDOUT,
            )
        )
    except subprocess.CalledProcessError as e:
        details = e.output.decode(errors="replace") if e.output else str(e)
        raise RuntimeError(f"Failed to read audio duration: {details}")


def normalize_audio(audio_path: str) -> str:
    """
    Normalize audio to 16kHz mono PCM WAV for accurate and fast chunking.
    Returns path to normalized wav file.
    """
    base, _ = os.path.splitext(audio_path)
    normalized_path = f"{base}_normalized.wav"

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", audio_path,
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                normalized_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        details = e.stderr.decode(errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"ffmpeg failed to normalize audio: {details}")

    return normalized_path


def chunk_audio(
    audio_path: str,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """
    Splits audio into chunks.
    Returns original file if shorter than chunk_length.
    """
    normalized_path = normalize_audio(audio_path)
    duration = get_audio_duration(normalized_path)

    if duration <= chunk_length:
        return [normalized_path]

    base, _ = os.path.splitext(normalized_path)
    output_dir = f"{base}_chunks"
    os.makedirs(output_dir, exist_ok=True)

    chunks = []
    total_chunks = math.ceil(duration / chunk_length)

    for i in range(total_chunks):
        start = max(0, i * chunk_length - overlap)
        out_file = os.path.join(output_dir, f"chunk_{i}.wav")

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss", str(start),
                    "-i", normalized_path,
                    "-t", str(chunk_length),
                    # PCM WAV supports accurate and fast stream copy
                    "-c", "copy",
                    out_file,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            details = e.stderr.decode(errors="replace") if e.stderr else str(e)
            raise RuntimeError(f"ffmpeg failed to create chunk {i}: {details}")


        chunks.append(out_file)

    return chunks
