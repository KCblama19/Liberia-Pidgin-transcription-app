from faster_whisper import WhisperModel
import os
from threading import Lock
from .interview_intelligence import is_question, detect_speaker
from django.conf import settings

_DEVICE = "cpu"
_COMPUTE_TYPE = "int8"

_PROFILES = {
    # Best for running multiple Celery workers in parallel
    "multi_job": {"cpu_threads": 3, "num_workers": 1},
    # Best for running a single worker and one transcription at a time
    "single_job": {"cpu_threads": 6, "num_workers": 2},
}


def _get_profile_settings() -> dict:
    """
    Load the transcription profile from Django settings
    or the environment
    """
    profile = getattr(settings, "TRANSCRIBE_PROFILE", None) or os.environ.get("TRANSCRIBE_PROFILE", "multi_job")
    profile = profile.strip().lower()
    return _PROFILES.get(profile, _PROFILES["multi_job"])

_model = None
_model_lock = Lock()

def get_model() -> WhisperModel:
    """
    Lazily load Faster-Whisper once per process.
    
    The lock only protexts model initialization
    Transcription itself is intentionally performed
    sequentially within a task
    """
    global _model
    
    if _model is None:
        with _model_lock:
            if _model is None:
                profile_settings = _get_profile_settings()
               
                _model = WhisperModel(
                    "systran/faster-whisper-medium",
                    device=_DEVICE,
                    compute_type=_COMPUTE_TYPE,
                    cpu_threads=profile_settings["cpu_threads"],
                    num_workers=profile_settings["num_workers"],
                    local_files_only=True,
                )
    return _model

def transcribe_chunk(audio_path: str, fast_mode: bool = False) -> list[dict]:
    """
    Transcribe one normalized audio chunk.
    
    Returned timestamps are relative to the beginning
    of this chunk. The pipeline is responsible for 
    applying the chunk's absolute start offset
    """
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(
            f"Audio file does not exist: {audio_path}"
        )

    model = get_model()
    beam_size = 1 if fast_mode else 5

    segments, _info = model.transcribe(
        audio_path,
        beam_size=beam_size,
        temperature=0.0,
        vad_filter=False,
        condition_on_previous_text=False,
        language="en",
    )

    results: list[dict] = []
    
    for seg in segments:
        text = seg.text.strip()
        if len(text) < 2:
            continue

        results.append({
            "start": seg.start,
            "end": seg.end,
            "original": text,
            "english": "",  # It will later contain the normalized text
            "speaker": detect_speaker(text),
            "type": "Question" if is_question(text) else "Answer",
        })

    return results
