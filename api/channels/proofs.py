"""Proof files: screenshots and PDFs the child adds to their case.

Files are kept under MEDIA_ROOT/proof and listed in the case's evidence chain, so each one
is tamper-evident like every other piece of evidence. The file type is checked from the
file's own first bytes, never from its name.
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

KIND = "proof_file"
MAX_BYTES = 8 * 1024 * 1024
_FILE = re.compile(r"^proof/[0-9a-f]{32}\.(jpg|png|webp|pdf)$")


def sniff(data: bytes):
    """(extension, content type) for a JPEG, PNG, WebP or PDF, otherwise None."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg", "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    if data[:5] == b"%PDF-":
        return "pdf", "application/pdf"
    return None


def save(data: bytes, extension: str, content_type: str) -> dict:
    name = f"proof/{uuid.uuid4().hex}.{extension}"
    path = Path(settings.MEDIA_ROOT) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "type": content_type, "at": timezone.now().isoformat(),
    }


def discard(note: dict) -> None:
    file_path(note["file"]).unlink(missing_ok=True)


def file_path(name: str) -> Path:
    if not _FILE.match(name or ""):
        raise ValueError("not a proof file")
    return Path(settings.MEDIA_ROOT) / name


def attach(case, note: dict) -> None:
    add_evidence(case, KIND, json.dumps(note, sort_keys=True))


def checked(note: dict, check) -> dict:
    """The note with the automatic check beside it. The check is a hint for the helper, never a verdict."""
    return {**note, "check": check} if check else note


def for_case(case) -> list:
    items = []
    for e in case.evidence.filter(kind=KIND).order_by("id"):
        try:
            data = json.loads(e.value)
        except ValueError:
            continue
        items.append({
            "id": e.id, "at": parse_datetime(data.get("at", "")), "type": data.get("type", ""),
            "is_image": str(data.get("type", "")).startswith("image/"), "kb": max(1, int(data.get("bytes", 0)) // 1024),
            "check": data.get("check") or None,
        })
    return items
