"""Turns page details sent by the browser extension (or share button) into evidence.

Only http(s) links are kept, text is trimmed, and a screenshot is stored as a file
named by its SHA-256 hash. Each item is added once per case.
"""
import base64
import binascii
import hashlib
import re
from pathlib import Path

from django.conf import settings

from core.evidence import add_evidence

MAX_TEXT = 500
MAX_SCREENSHOT_BYTES = 3 * 1024 * 1024
IMAGE_DATA_URL = re.compile(r"^data:image/(png|jpeg|webp);base64,(.+)$", re.S)
TEXT_FIELDS = {"url": "url", "platform": "platform", "title": "page_title", "handle": "handle", "selection": "selection"}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _clean(kind, value):
    if not isinstance(value, str):
        return None
    value = value.strip()[:MAX_TEXT]
    if not value:
        return None
    if kind == "url" and not re.match(r"^https?://", value, re.I):
        return None
    return value


def _save_screenshot(data_url):
    m = IMAGE_DATA_URL.match(data_url or "")
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except (binascii.Error, ValueError):
        return None
    if not raw or len(raw) > MAX_SCREENSHOT_BYTES:
        return None
    digest = hashlib.sha256(raw).hexdigest()
    folder = Path(settings.MEDIA_ROOT) / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{digest}.{m.group(1)}").write_bytes(raw)
    return f"sha256:{digest} bytes:{len(raw)} type:image/{m.group(1)}"


PLATFORM_DOMAINS = {"instagram.com": "instagram", "tiktok.com": "tiktok", "snapchat.com": "snapchat",
                    "x.com": "x", "twitter.com": "x", "linkedin.com": "linkedin", "facebook.com": "facebook",
                    "web.whatsapp.com": "whatsapp", "discord.com": "discord", "roblox.com": "roblox",
                    "youtube.com": "youtube"}


def platform_from_url(url):
    """Same rule as extension/platform.js: exact domain or a real subdomain only."""
    from urllib.parse import urlparse
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    for domain, name in PLATFORM_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def attach_meta(case, meta):
    if not isinstance(meta, dict) or not meta:
        return []
    if not meta.get("platform") and isinstance(meta.get("url"), str):
        meta = {**meta, "platform": platform_from_url(meta["url"])}
    have = set(case.evidence.values_list("kind", "value_sha256"))
    added = []
    items = [(kind, _clean(kind, meta.get(key))) for key, kind in TEXT_FIELDS.items()]
    if meta.get("screenshot"):
        items.append(("screenshot", _save_screenshot(meta["screenshot"])))
    for kind, value in items:
        if value is None or (kind, _sha(value)) in have:
            continue
        added.append(add_evidence(case, kind, value))
    return added
