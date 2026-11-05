"""Rules-only triage: pick floors plus the keyword lexicon.

Works with no AI at all. The AI service (Phase 2) can raise severity on top of
this, never lower it.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml
from django.conf import settings

from core.harm import pick_severity

AUTHORITY_FLAG = "authority"


@lru_cache
def lexicon() -> dict:
    return yaml.safe_load(settings.LEXICON_PATH.read_text(encoding="utf8"))


def normalise_text(text: str) -> str:
    words = re.sub(r"[^\w\s]", " ", (text or "").lower()).split()
    shorthand = lexicon().get("shorthand", {})
    return " ".join(shorthand.get(w, w) for w in words)


def _contains(text: str, term: str) -> bool:
    # Whole words only, so "bet" does not match "better".
    return re.search(rf"(?<!\w){re.escape(normalise_text(term))}(?!\w)", text) is not None


@dataclass
class RuleResult:
    severity: int
    flags: list = field(default_factory=list)
    role_hint: str | None = None


def apply_rules(text: str, pick=None) -> RuleResult:
    norm = normalise_text(text)
    lex = lexicon()
    severity = pick_severity(pick)
    flags = []
    for name, spec in lex["flags"].items():
        terms = [t for lang_terms in spec["terms"].values() for t in lang_terms]
        if any(_contains(norm, t) for t in terms):
            flags.append(name)
            severity = max(severity, spec.get("floor", 0))
    for combo in lex.get("combinations", []):
        if all(f in flags for f in combo["all_of"]):
            severity = max(severity, combo["floor"])
    role_hint = "authority" if AUTHORITY_FLAG in flags else None
    return RuleResult(severity=severity, flags=flags, role_hint=role_hint)
