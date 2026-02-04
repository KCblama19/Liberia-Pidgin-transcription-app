import re
from .kolokwa_normalizer import normalize

def detect_speaker(text: str) -> str:
    match = re.search(r"\b(P\d+)\b", text)
    return match.group(1) if match else "UNKNOWN"

def is_question(text: str) -> bool:
    t = text.lower()
    return "?" in t or any(q in t for q in ("what", "why", "how", "when", "where", "who"))

def build_segments(raw_segments: list, normalizer_func=normalize, offset: float = 0.0) -> list:
    """
    Convert raw Whisper segments into structured interview segments with type and speaker color.
    """
    structured = []

    for i, s in enumerate(raw_segments):
        text = s.get("text") or s.get("original") or ""
        speaker = detect_speaker(text)
        segment_type = "Question" if is_question(text) else "Answer"

        # Assign a color for each speaker
        color_classes = [
            "bg-red-100 text-red-800",
            "bg-green-100 text-green-800",
            "bg-blue-100 text-blue-800",
            "bg-yellow-100 text-yellow-800",
            "bg-purple-100 text-purple-800",
        ]
        speaker_index = int(re.sub(r"\D", "", speaker) or 0) % len(color_classes)
        speaker_color = color_classes[speaker_index]

        structured.append(
            {
                "start": s.get("start", 0) + offset,
                "end": s.get("end", 0) + offset,
                "speaker": speaker,
                "speaker_color": speaker_color,
                "type": segment_type,
                "original": text,
                "english": normalizer_func(text),
            }
        )

    return structured

