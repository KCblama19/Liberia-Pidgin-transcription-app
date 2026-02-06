import re
from .regex_normalizer import normalize_text

def detect_speaker(text: str) -> str:
    """
    Detect explicit speaker tags only at the start of the segment, e.g. "P1:" or "P2 -".
    Avoid matching tags that appear inside normal sentences.
    """
    match = re.match(r"^\s*(P\d+)\b(\s*[:\-])?", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"

def is_question(text: str) -> bool:
    t = text.lower()
    return "?" in t or any(q in t for q in ("what", "why", "how", "when", "where", "who"))

def build_segments(raw_segments: list, normalizer_func=normalize_text, offset: float = 0.0) -> list:
    """
    Convert raw Whisper segments into structured interview segments with type and speaker color.
    """
    structured = []
    consecutive_unknown_questions = 0

    for i, s in enumerate(raw_segments):
        text = s.get("text") or s.get("original") or ""
        speaker = detect_speaker(text)
        segment_type = "Question" if is_question(text) else "Answer"

        if speaker == "UNKNOWN" and segment_type == "Question":
            consecutive_unknown_questions += 1
            if consecutive_unknown_questions >= 2:
                speaker = "INTERVIEWER"
        else:
            consecutive_unknown_questions = 0

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

