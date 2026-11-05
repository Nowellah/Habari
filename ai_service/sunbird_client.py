"""Thin wrapper around the Sunbird AI API. Every function returns None when no
SUNBIRD_TOKEN is set or the call fails, so callers always have a fallback.

The endpoint paths changed in 2026 (see build plan §1.5). They are settings so a
change touches only the .env file. CONFIRM THEM against docs.sunbird.ai before use:
this wrapper has not been tested against the live API yet.
"""
import os

import requests

BASE = os.getenv("SUNBIRD_BASE_URL", "https://api.sunbird.ai")
LANGUAGE_PATH = os.getenv("SUNBIRD_LANGUAGE_PATH", "/tasks/language_id")
TRANSLATE_PATH = os.getenv("SUNBIRD_TRANSLATE_PATH", "/tasks/translate")
TIMEOUT = float(os.getenv("SUNBIRD_TIMEOUT", "4"))

# Sunbird uses 3-letter codes; Habari uses short codes.
TO_HABARI = {"lug": "lg", "nyn": "rn", "eng": "en", "swa": "sw"}
TO_SUNBIRD = {v: k for k, v in TO_HABARI.items()}


def _token():
    return os.getenv("SUNBIRD_TOKEN", "").strip()


def _post(path, payload):
    if not _token():
        return None
    try:
        r = requests.post(BASE + path, json=payload, timeout=TIMEOUT,
                          headers={"Authorization": f"Bearer {_token()}"})
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def enabled() -> bool:
    return bool(_token())


def language_id(text):
    data = _post(LANGUAGE_PATH, {"text": text})
    if not data:
        return None
    code = data.get("language") or data.get("output", {}).get("language")
    return {"language": TO_HABARI.get(code, code)} if code else None


def translate(text, source, target):
    data = _post(TRANSLATE_PATH, {
        "source_language": TO_SUNBIRD.get(source, source),
        "target_language": TO_SUNBIRD.get(target, target),
        "text": text,
    })
    if not data:
        return None
    out = data.get("text") or data.get("output", {}).get("translated_text")
    return out or None
