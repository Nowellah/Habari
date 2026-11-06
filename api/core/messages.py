"""Child-facing reply texts, loaded from shared/messages_<lang>.json.

A language with no file, or a text missing from its file, falls back to English, so a
half-translated language never breaks a reply.
"""
import json
from functools import lru_cache

from django.conf import settings


@lru_cache
def _messages(lang: str) -> dict:
    path = settings.SHARED_DIR / f"messages_{lang}.json"
    if not path.exists():
        path = settings.SHARED_DIR / "messages_en.json"
    return json.loads(path.read_text(encoding="utf8"))


@lru_cache
def reply_languages() -> frozenset:
    """Languages children can be answered in: those with their own messages file."""
    return frozenset(p.stem.split("_", 1)[1] for p in settings.SHARED_DIR.glob("messages_*.json"))


def text_for(key: str, lang: str = "en"):
    """The raw text for a key in this language, else English. None if neither has it."""
    for source in (_messages(lang or "en"), _messages("en")):
        if key in source:
            return source[key]
    return None


def msg(key: str, lang: str = "en", **kw) -> str:
    return text_for(key, lang).format(helpline=settings.HELPLINE_NUMBER, **kw)


def label(name: str, lang: str = "en") -> str:
    """A button label in this language, else English."""
    return (_messages(lang or "en").get("labels") or {}).get(name) or _messages("en")["labels"][name]


def child_language(case) -> str:
    """The language to write to this child in: theirs if we have replies in it, else English."""
    lang = (case.reporter.language if case.reporter else "") or case.language or "en"
    return lang if lang in reply_languages() else "en"


def status_words(case, lang: str = "en") -> str:
    """Plain status in kind words. Never includes case details."""
    status = (text_for("status", lang) or {}).get(case.status) or _messages("en")["status"][case.status]
    return f"{text_for('case_word', lang) or 'Case'} {case.code}: " + status
