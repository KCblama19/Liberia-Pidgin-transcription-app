import re

# Conservative phrase-based normalization.
#
# Important:
# We avoid aggressive single-word substitutions because
# words such as "na", "da", and "dey" can depend heavily
# on context.
#
# Longer and more specific phrases should appear first.
KOLOKWA_PATTERNS = [
    (
        r"\bI\s+na\s+know\b",
        "I do not know",
    ),
    (
        r"\bI\s+now\s+know\b",
        "I do not know",
    ),
    (
        r"\bI\s+na\s+there\b",
        "I am not there",
    ),
    (
        r"\bI\s+alright\b",
        "I am alright",
    ),
    (
        r"\bhow\s+you\s+doing\b",
        "how are you doing",
    ),
    (
        r"\bsmall[\s-]+small\b",
        "gradually",
    ),
    (
        r"\bmy\s+pa\b",
        "my father",
    ),
    (
        r"\bshe[\s-]+self\b",
        "herself",
    ),
    (
        r"\bhim[\s-]+self\b",
        "himself",
    ),
    (
        r"\bman[\s-]+self\b",
        "himself",
    ),
    (
        r"\bgirl[\s-]+self\b",
        "herself",
    ),

    # Known transcription corrections.
    (
        r"\bHappo\b",
        "Harper",
    ),
]


COMPILED_PATTERNS = [
    (
        re.compile(
            pattern,
            re.IGNORECASE,
        ),
        replacement,
    )
    for pattern, replacement in KOLOKWA_PATTERNS
]


def normalize(text: str) -> str:
    """
    Apply conservative Liberian English / Kolokwa
    normalization.

    The original transcript is not modified elsewhere.
    This function only produces the normalized English
    version.
    """
    if not text:
        return text

    output = text

    for pattern, replacement in COMPILED_PATTERNS:
        output = pattern.sub(
            replacement,
            output,
        )

    # Clean accidental repeated whitespace.
    output = re.sub(
        r"\s+",
        " ",
        output,
    ).strip()

    # Capitalize the first character while preserving
    # the rest of the transcription.
    if output:
        output = (
            output[0].upper()
            + output[1:]
        )

    return output