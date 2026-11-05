"""Child-facing reply texts, loaded from shared/messages_<lang>.json."""
import json
from functools import lru_cache

from django.conf import settings


@lru_cache
def _messages(lang: str) -> dict:
    path = settings.SHARED_DIR / f"messages_{lang}.json"
    if not path.exists():
        path = settings.SHARED_DIR / "messages_en.json"
    return json.loads(path.read_text(encoding="utf8"))


def msg(key: str, lang: str = "en", **kw) -> str:
    return _messages(lang)[key].format(helpline=settings.HELPLINE_NUMBER, **kw)


def status_words(case, lang: str = "en") -> str:
    """Plain status in kind words. Never includes case details."""
    return f"Case {case.code}: " + _messages(lang)["status"][case.status]
