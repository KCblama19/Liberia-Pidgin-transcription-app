import re

# Expanded map for common Liberian English / Kolokwa expressions
KOLOKWA_PATTERNS = {
    r"\bI na know\b": "I do not know",
    r"\bI now know\b": "I don't know",
    r"\bAnna\b": "I don't",
    r"\bI na there\b": "I am not there",
    r"\bla me\b": "It is I",
    r"\bmy pa\b": "my father",
    r"\bsmall-small\b": "gradually",
    r"\bda one\b": "that one",
    r"\bla one\b": "that one",
    r"\bplenty\b": "many",
    r"\bhard\b": "difficult",
    r"\bwe try\b": "we tried",
    r"\bhow you doing\b": "how are you",
    r"\bI alright\b": "I am okay",
    r"\bda\b": "that",
    r"\bla\b": "that",
    r"\bna\b": "not",
    r"\bdis\b": "this",
    r"\blay\b": "this",
    r"\bdat\b": "that",
    r"\bmeh\b": "me",
    r"\bshe-self\b": "herself",
    r"\bhim-self\b": "himself",
    r"\bman-self\b": "himself",
    r"\bgirl-self\b": "herself",
    r"\bwen\b": "when",
    r"\bwat\b": "what",
    r"\wetin\b": "what",
    r"\bwi\b": "we",
    r"\bdey\b": "is",
}

# Precompile regex patterns for performance
COMPILED_PATTERNS = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in KOLOKWA_PATTERNS.items()]

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
