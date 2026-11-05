"""Calls the AI service. Returns None on any failure so the caller can fall back."""
import requests
from django.conf import settings


def triage(text, pick, language):
    try:
        r = requests.post(
            f"{settings.AI_SERVICE_URL}/triage",
            json={"text": text or "", "pick": pick or None, "language": language or None},
            timeout=settings.AI_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data if isinstance(data, dict) and "severity" in data else None
    except (requests.RequestException, ValueError):
        return None


def voice_available() -> bool:
    """True when the AI service is up and has a speech-to-text engine set up."""
    try:
        r = requests.get(f"{settings.AI_SERVICE_URL}/health", timeout=1.5)
        return r.status_code == 200 and bool(r.json().get("speech_to_text"))
    except (requests.RequestException, ValueError, AttributeError):
        return False


def transcribe(audio: bytes, filename: str, language=None):
    """Voice note to text via the AI service. None if it is down or has no engine."""
    try:
        r = requests.post(
            f"{settings.AI_SERVICE_URL}/transcribe",
            files={"audio": (filename or "voice", audio)},
            data={"language": language or ""},
            timeout=max(settings.AI_TIMEOUT, 60),
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data if isinstance(data, dict) and data.get("text") else None
    except (requests.RequestException, ValueError):
        return None


def summarise(messages):
    """Officer summary, timeline and details. None if the AI service is down."""
    try:
        r = requests.post(f"{settings.AI_SERVICE_URL}/summarise", json={"messages": messages},
                          timeout=settings.AI_TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        return data if isinstance(data, dict) and "summary" in data else None
    except (requests.RequestException, ValueError):
        return None
