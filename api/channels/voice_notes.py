"""Voice notes: the original recording is kept for the officer, next to the words the bot understood.

The audio is stored under MEDIA_ROOT/voice and listed in the case's evidence chain,
so it is tamper-evident like every other piece of evidence.
"""
import hashlib
import json
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.evidence import add_evidence

KIND = "voice_note"
_FILE = re.compile(r"^voice/[0-9a-f]{32}\.wav$")
_CUES = {"seconds": 600, "level": 100, "peak": 100, "pauses": 99}


def is_wav(data: bytes) -> bool:
    return len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def clean_cues(raw) -> dict:
    """Keep only small whole numbers measured on the device; ignore anything else."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, limit in _CUES.items():
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= limit:
            out[key] = int(value)
    return out


def save(data: bytes, cues: dict) -> dict:
    name = f"voice/{uuid.uuid4().hex}.wav"
    path = Path(settings.MEDIA_ROOT) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "cues": cues, "at": timezone.now().isoformat(),
    }


def discard(note: dict) -> None:
    audio_path(note["file"]).unlink(missing_ok=True)


def audio_path(name: str) -> Path:
    if not _FILE.match(name or ""):
        raise ValueError("not a voice note file")
    return Path(settings.MEDIA_ROOT) / name


def attach(case, notes: list) -> None:
    """Add each note to the case once; a note already on the case is skipped."""
    for note in notes:
        value = json.dumps(note, sort_keys=True)
        digest = hashlib.sha256(value.encode()).hexdigest()
        if not case.evidence.filter(kind=KIND, value_sha256=digest).exists():
            add_evidence(case, KIND, value)


def describe(cues: dict) -> str:
    """Plain words for the officer. A rough hint from the recording, never a diagnosis."""
    parts = []
    if "seconds" in cues:
        parts.append(f"{cues['seconds']} s long")
    if "level" in cues:
        parts.append("quiet voice" if cues["level"] < 3 else "raised voice" if cues["level"] >= 12 else "normal volume")
    if cues.get("pauses"):
        parts.append(f"{cues['pauses']} long pause{'s' if cues['pauses'] > 1 else ''}")
    return ", ".join(parts)


def for_case(case) -> list:
    notes = []
    for e in case.evidence.filter(kind=KIND).order_by("id"):
        try:
            data = json.loads(e.value)
        except ValueError:
            continue
        notes.append({"id": e.id, "at": parse_datetime(data.get("at", "")), "cues": describe(data.get("cues", {}))})
    return notes
