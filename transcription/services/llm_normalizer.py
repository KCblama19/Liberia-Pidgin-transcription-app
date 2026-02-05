import os
import json
import requests


_SYSTEM_PROMPT = (
    "You are a normalization assistant. Your task is to convert Liberian Kolokwa / "
    "Liberian English into clear standard English. This is NOT translation or paraphrasing. "
    "Preserve the original meaning and intent exactly. Do NOT summarize. Do NOT add or remove "
    "information. Keep sentence structure as close as possible to the original."
)

_EXAMPLES = [
    ("I na know", "I do not know"),
    ("We dey go market tomorrow", "We are going to the market tomorrow"),
    ("He say he na coming today", "He said he is not coming today"),
]


def _build_prompt(text: str) -> str:
    examples = "\n".join([f"Input: {src}\nOutput: {dst}" for src, dst in _EXAMPLES])
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        "Examples:\n"
        f"{examples}\n\n"
        "Now normalize the following text:\n"
        f"Input: {text}\n"
        "Output:"
    )


def llm_normalize_to_standard_english(text: str) -> str:
    """
    Normalize Liberian Kolokwa / Liberian English to standard English using an LLM.
    This function is only meant to be called by the translate view on user action.
    """
    api_url = os.environ.get("LLM_API_URL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()

    if not api_url or not api_key:
        raise RuntimeError("LLM_API_URL and LLM_API_KEY must be set to use LLM normalization.")

    prompt = _build_prompt(text)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Support common response shapes
    if isinstance(data, dict):
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"].strip()
        if "output_text" in data:
            return str(data["output_text"]).strip()

    raise RuntimeError("Unexpected LLM response format.")
