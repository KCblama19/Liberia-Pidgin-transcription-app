import re

# Expanded map for common Liberian English / Kolokwa expressions
# Order matters: longer/more specific phrases should come first.
KOLOKWA_PATTERNS = [
    (r"\bI na know\b", "I do not know"),
    (r"\bI now know\b", "I don't know"),
    (r"\bI na there\b", "I am not there"),
    (r"\bAnna\b", "I don't"),
    (r"\bla me\b", "It is I"),
    (r"\bmy pa\b", "my father"),
    (r"\bsmall-small\b", "gradually"),
    (r"\bda one\b", "that one"),
    (r"\bla one\b", "that one"),
    (r"\bhow you doing\b", "how are you"),
    (r"\bI alright\b", "I am okay"),
    (r"\bwe try\b", "we tried"),
    (r"\bplenty\b", "many"),
    (r"\bhard\b", "difficult"),
    (r"\bshe-self\b", "herself"),
    (r"\bhim-self\b", "himself"),
    (r"\bman-self\b", "himself"),
    (r"\bgirl-self\b", "herself"),
    (r"\bwetin\b", "what"),
    (r"\bwen\b", "when"),
    (r"\bwat\b", "what"),
    (r"\bwi\b", "we"),
    (r"\bdey\b", "is"),
    (r"\bking\b", "came"),
    (r"\bHappo\b", "Harper"),
    (r"\bPinget\b", "bring it"),
    (r"\bNassau\b", "that side"),
    (r"\bfishers\b", "freezers"),
    # Short tokens last to reduce over-matching
    (r"\bda\b", "that"),
    (r"\bla\b", "that"),
    (r"\bdis\b", "this"),
    (r"\blay\b", "this"),
    (r"\bdat\b", "that"),
    (r"\bmeh\b", "me"),
    (r"\bko\b", "call"),
    (r"\bpo\b", "people"),
    (r"\bna\b", "not"),
]

# Precompile regex patterns for performance
COMPILED_PATTERNS = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in KOLOKWA_PATTERNS]


def normalize(text: str) -> str:
    """
    Converts Liberian English / Kolokwa phrases into standard English.
    """
    out = text

    # Apply all pattern replacements
    for pattern, replacement in COMPILED_PATTERNS:
        out = pattern.sub(replacement, out)

    # Capitalize first letter of the sentence
    if out:
        out = out[0].upper() + out[1:]

    return out
