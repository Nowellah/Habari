"""Loads the shared harm picker and SLA files used by every channel."""
import json
from functools import lru_cache

from django.conf import settings


@lru_cache
def harm_picker() -> dict:
    return json.loads((settings.SHARED_DIR / "harm_picker.json").read_text(encoding="utf8"))


@lru_cache
def picks() -> dict:
    return {p["id"]: p for p in harm_picker()["picks"]}


def pick_severity(pick_id) -> int:
    p = picks().get(str(pick_id)) if pick_id else None
    return p["default_severity"] if p else 1


@lru_cache
def sla_rules() -> dict:
    data = json.loads((settings.SHARED_DIR / "sla_rules.json").read_text(encoding="utf8"))
    return {int(k): v for k, v in data.items() if not k.startswith("_")}
