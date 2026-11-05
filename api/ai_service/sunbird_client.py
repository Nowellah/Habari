"""Thin wrapper around the Sunbird AI API. Every function returns None when no
SUNBIRD_TOKEN is set or the call fails, so callers always have a fallback.

The endpoint paths changed in 2026 (see build plan §1.5). They are settings so a
change touches only the .env file. The speech path and fields follow docs.sunbird.ai;
the language and translate calls have not been checked against the live API.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

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


STT_PATH = os.getenv("SUNBIRD_STT_PATH", "/tasks/audio/transcriptions")


STT_DEFAULT_LANGUAGE = os.getenv("SUNBIRD_STT_LANGUAGE", "eng")


def audio_part(audio: bytes):
    """File name and media type taken from the first bytes, so the API gets the real format."""
    head = audio[:12]
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "voice.wav", "audio/wav"
    if head[:4] == b"OggS":
        return "voice.ogg", "audio/ogg"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "voice.mp3", "audio/mpeg"
    if head[4:8] == b"ftyp":
        return "voice.m4a", "audio/mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "voice.webm", "audio/webm"
    return "voice.ogg", "audio/ogg"


def stt_language(language):
    """The API needs a language code and does not detect one reliably."""
    code = TO_SUNBIRD.get(language or "", language or "")
    return code if code in TO_SUNBIRD.values() else STT_DEFAULT_LANGUAGE


def transcribe(audio: bytes, language):
    """Speech to text for English, Luganda, Runyankore or Swahili. None on any failure."""
    if not _token():
        return None
    name, media_type = audio_part(audio)
    try:
        r = requests.post(BASE + STT_PATH, timeout=60,
                          headers={"Authorization": f"Bearer {_token()}"},
                          files={"audio": (name, audio, media_type)},
                          data={"language": stt_language(language)})
        r.raise_for_status()
        data = r.json()
    except requests.HTTPError as exc:
        log.warning("Sunbird speech-to-text refused the request: HTTP %s", exc.response.status_code)
        return None
    except (requests.RequestException, ValueError) as exc:
        log.warning("Sunbird speech-to-text failed: %s", type(exc).__name__)
        return None
    text = data.get("audio_transcription") or data.get("text") or None
    if not text:
        log.warning("Sunbird speech-to-text returned no words")
    return text


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
