import os
import math
import subprocess
import logging
import shutil
from typing import TypedDict


DEFAULT_CHUNK_LENGTH = 600  # seconds
DEFAULT_OVERLAP = 2

logger = logging.getLogger("transcription")

class AudioChunk(TypedDict):
    path: str
    start: float
    duration: float

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
        details = (
            e.output.decode(errors="replace") 
            if e.output 
            else str(e)
        )
        logger.error(
            "Failed to read audio duration for %s: %s",
            audio_path,
            details
        )
        raise RuntimeError(
            f"Failed to read audio duration: {details}"
        ) from e


def normalize_audio(audio_path: str) -> str:
    """
    Normalize audio to 
    
    - 16kHz 
    - mono 
    - PCM WAV 
    for accurate and fast chunking and predictable Whisper-friendly format.
    
    Returns the normalized file path.
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
        details = (
            e.stderr.decode(errors="replace") 
            if e.stderr 
            else str(e)
        )
        logger.error(
            "FFmpeg failed to normalize %s: %s",
            audio_path, 
            details
        )
        raise RuntimeError(
            f"ffmpeg failed to normalize audio: {details}"
        ) from e

    return normalized_path


def chunk_audio(
    audio_path: str,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    overlap: int = DEFAULT_OVERLAP,
) -> list[AudioChunk]:
    """
    Splits normalized audio into overlapping chunks.
    
    Every returned chunk contains:
    
    - path: absolute file path
    - start: absolute start time in the original audio
    - duration: actual chunk duration
    
    Returns original file if shorter than chunk_length.
    """
    if chunk_length <= 0:
        raise ValueError(
            "chunk_length must be greater than zero."
        )
    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative"
        )
    if overlap >= chunk_length:
        raise ValueError(
            "overlap must be smaller than chunk length"
        )
        
    normalized_path = normalize_audio(audio_path)
    duration = get_audio_duration(normalized_path)

    if duration <= 0:
        raise RuntimeError(
            f"Audio duration is invalid: {duration}"
        )
        
    if duration <= chunk_length:
        return [
            {
                "path": normalized_path,
                "start": 0.0,
                "duration": duration
            }
        ]

    base, _ = os.path.splitext(normalized_path)
    output_dir = f"{base}_chunks"
    
    # Remove stale chunks from a previous transcription attempt
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        
    os.makedirs(output_dir, exist_ok=True)

    chunks: list[AudioChunk] = []
    
    step = chunk_length - overlap
    total_chunks = math.ceil(
        (duration - overlap) / step
    )

    for i in range(total_chunks):
        start = i * step
        
        if start >= duration:
            break
        
        actual_duration = min(
            chunk_length,
            duration - start,
        )
        out_file = os.path.join(output_dir, f"chunk_{i:04d}.wav")

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(start),
                    "-i",
                    normalized_path,
                    "-t",
                    str(actual_duration),
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    out_file,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            details = (
                e.stderr.decode(errors="replace") 
                if e.stderr else str(e)
            )
            logger.error(
                "FFmpeg failed to create chunk %s: %s",
                i, 
                details,
            )
            raise RuntimeError(f"ffmpeg failed to create chunk {i}: {details}")


        chunks.append(
            {
                "path": out_file,
                "start": float(start),
                "duration": float(actual_duration),
            }
        )

    return chunks
