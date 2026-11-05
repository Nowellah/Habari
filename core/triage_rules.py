"""Rules-only triage: pick floors plus the keyword lexicon.

Works with no AI at all. The AI service can raise severity on top of this,
never lower it. The keyword engine itself lives in ai_service/lexicon_engine.py
so the web app and the AI service always agree.
"""
from dataclasses import dataclass, field

from ai_service import lexicon_engine
from core.harm import pick_severity

normalise_text = lexicon_engine.normalise_text


@dataclass
class RuleResult:
    severity: int
    flags: list = field(default_factory=list)
    role_hint: str | None = None


def apply_rules(text: str, pick=None) -> RuleResult:
    flags, floor = lexicon_engine.match(text)
    severity = max(pick_severity(pick), floor)
    role_hint = "authority" if "authority" in flags else None
    return RuleResult(severity=severity, flags=flags, role_hint=role_hint)
