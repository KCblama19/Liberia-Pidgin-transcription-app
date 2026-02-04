from faster_whisper import WhisperModel

_translation_model = None

def get_translation_model():
    global _translation_model
    if _translation_model is None:
        # This line will try to download the model if it's not already local
        _translation_model = WhisperModel(
            "base",  # or local path if available
            device="cpu",
            compute_type="int8"
        )
    return _translation_model

def translate_text(text):
    model = get_translation_model()
    segments, _ = model.transcribe(
        None,
        task="translate",
        language="en",
        initial_prompt=(
            "Convert Liberian Kolokwa mixed with English into "
            "clear standard English without changing meaning."
        ),
        condition_on_previous_text=False,
        text=text
    )
    return " ".join(seg.text for seg in segments)
