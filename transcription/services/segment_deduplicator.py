import re
from difflib import SequenceMatcher


def _clean_text(text: str) -> str:
    """
    Normalize text for duplicate comparison.

    This is only used for comparison. It does not
    modify the transcript shown to the user.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _similarity(
    first: str,
    second: str,
) -> float:
    """
    Return a similarity score between 0 and 1.
    """
    return SequenceMatcher(
        None,
        _clean_text(first),
        _clean_text(second),
    ).ratio()


def deduplicate_segments(
    segments: list[dict],
    similarity_threshold: float = 0.92,
) -> list[dict]:
    """
    Remove duplicate transcript segments produced by
    overlapping audio chunks.

    A segment is treated as a duplicate only when:

    1. Its timestamp overlaps or nearly touches the
       previous segment, and
    2. Its text is highly similar.

    The first occurrence is preserved.
    """
    if not segments:
        return []

    sorted_segments = sorted(
        segments,
        key=lambda segment: (
            segment["start"],
            segment["end"],
        ),
    )

    cleaned: list[dict] = []

    for current in sorted_segments:
        if not cleaned:
            cleaned.append(current)
            continue

        previous = cleaned[-1]

        timestamps_touch = (
            current["start"]
            <= previous["end"] + 0.5
        )

        text_similarity = _similarity(
            previous.get("original", ""),
            current.get("original", ""),
        )

        if (
            timestamps_touch
            and text_similarity >= similarity_threshold
        ):
            # Preserve the earliest segment but extend its
            # end time if the duplicate runs slightly longer.
            previous["end"] = max(
                previous["end"],
                current["end"],
            )

            continue

        cleaned.append(current)

    return cleaned