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
