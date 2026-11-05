"""Speech to text. Picks an engine by language (build plan §1.5):

- Sunbird first when SUNBIRD_TOKEN is set (English, Luganda, Runyankore, Swahili)
- Whisper (needs AI_WHISPER_MODEL and faster-whisper) as the fallback

With no engine set up, get_transcriber() returns None and the child is asked to type.
"""
import io
import os
from functools import lru_cache

from ai_service import sunbird_client

_UNSET = object()
_override = _UNSET


def set_transcriber(fn):
    """Tests: force an engine (a function), or None for "no engine"."""
    global _override
    _override = fn


def reset_transcriber():
    global _override
    _override = _UNSET


@lru_cache
def _whisper():
    model = os.getenv("AI_WHISPER_MODEL", "").strip()
    if not model:
        return None
    try:
        from faster_whisper import WhisperModel  # optional, heavy
        return WhisperModel(model, device="auto", compute_type="int8")
    except Exception:
        return None


def _whisper_transcribe(audio, language):
    model = _whisper()
    if model is None:
        return None
    segments, info = model.transcribe(io.BytesIO(audio), language=language if language in ("en", "sw") else None)
    text = " ".join(s.text for s in segments).strip()
    return {"text": text, "language": getattr(info, "language", language), "engine": "whisper"} if text else None


def _sunbird_transcribe(audio, language):
    text = sunbird_client.transcribe(audio, language)
    return {"text": text, "language": language, "engine": "sunbird"} if text else None


def engines_available():
    names = []
    if sunbird_client.enabled():
        names.append("sunbird")
    if os.getenv("AI_WHISPER_MODEL", "").strip():
        names.append("whisper")
    return names


def get_transcriber():
    if _override is not _UNSET:
        return _override
    names = engines_available()
    if not names:
        return None

    def run(audio, language):
        for name in ("sunbird", "whisper"):
            if name not in names:
                continue
            out = (_sunbird_transcribe if name == "sunbird" else _whisper_transcribe)(audio, language)
            if out:
                return out
        return None

    return run
