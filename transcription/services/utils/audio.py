import os
import math
import subprocess

CHUNK_LENGTH_SECONDS = 5 * 60  # 5 minutes


def get_audio_duration_seconds(path: str) -> float:
    """
    Get audio duration in seconds using ffprobe (works for m4a/mp3/wav).
    """
    output = subprocess.check_output([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ])
    return float(output)


def split_audio(path: str, output_dir: str) -> list[str]:
    """
    Split audio into 5-minute chunks using ffmpeg.
    Returns list of chunk file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    duration = get_audio_duration_seconds(path)
    total_chunks = math.ceil(duration / CHUNK_LENGTH_SECONDS)

    chunks = []

    for i in range(total_chunks):
        start = i * CHUNK_LENGTH_SECONDS
        out_path = os.path.join(output_dir, f"chunk_{i}.mp3")

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", path,
                "-ss", str(start),
                "-t", str(CHUNK_LENGTH_SECONDS),
                out_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        chunks.append(out_path)

    return chunks