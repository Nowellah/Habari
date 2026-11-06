"""AI helpers for the case engine. They run in this process, with no separate service.

Every function returns None on any failure so the caller can fall back to its rules.
"""
import logging

from ai_service import speech, synthesis, vision
from ai_service.classifier import zero_shot
from ai_service.triage import triage as run_triage

logger = logging.getLogger("habari.ai")


def triage(text, pick, language):
    try:
        data = run_triage(text or "", pick=pick or None, language=language or None, classifier=zero_shot())
    except Exception as exc:  # noqa: BLE001 - a broken helper must never block a report
        logger.error("triage failed with %s", type(exc).__name__)
        return None
    return data if isinstance(data, dict) and "severity" in data else None


def check_proof(image: bytes, content_type: str, said: str, category: str = ""):
    """A rough match between a proof picture and the report. None when no check is set up or it failed."""
    return vision.check_proof(image, content_type, said, category)


def voice_available() -> bool:
    """True when a speech-to-text engine is set up."""
    return bool(speech.engines_available())


def transcribe(audio: bytes, filename: str, language=None):
    """Voice note to text. None if no engine is set up or it could not make out any words."""
    engine = speech.get_transcriber()
    if engine is None or not audio:
        return None
    try:
        out = engine(audio, language or None)
    except Exception as exc:  # noqa: BLE001 - speech engines fail in many ways
        logger.error("speech to text failed with %s", type(exc).__name__)
        return None
    text = ((out or {}).get("text") or "").strip()
    if not text:
        return None
    return {"text": text, "language": out.get("language") or language or "unknown", "engine": out.get("engine")}


def summarise(messages):
    """Officer summary, timeline and details."""
    try:
        data = synthesis.summarise(messages)
    except Exception as exc:  # noqa: BLE001
        logger.error("summary failed with %s", type(exc).__name__)
        return None
    return data if isinstance(data, dict) and "summary" in data else None
