"""Adapter between the rule engine and the case engine's triage contract.

The case engine speaks integer severities (1 to 4) and its own category names.
This module runs the rule engine on a message and returns the result in those
terms. It can only raise severity; it never lowers anything.
"""
import logging
from dataclasses import dataclass, field

from ai_service.engine.schemas import Category
from ai_service.engine.triage import safe_triage

logger = logging.getLogger("habari.ai")

# Rule engine category -> case engine category. "other" has no equivalent and
# leaves the case engine's own category untouched.
_CATEGORY_MAP = {
    Category.SELF_HARM: "self_harm",
    Category.IMMEDIATE_DANGER: "threats",
    Category.SEXTORTION: "sextortion",
    Category.GROOMING: "grooming",
    Category.HARASSMENT: "cyberbullying",
    Category.ACCOUNT_SCAM: "scam",
    Category.EXPOSURE: "inappropriate_content",
}
FLAG_PREFIX = "rule:"


@dataclass(frozen=True)
class Assessment:
    severity: int
    category: str | None
    confident: bool
    external_only: bool
    human_review: bool
    flags: list[str] = field(default_factory=list)


def _category(result) -> str | None:
    if result.category == Category.ABUSE:
        # Harm by a trusted adult must be routed outside the family and school.
        return "exposure_by_authority" if result.external_only else "threats"
    return _CATEGORY_MAP.get(result.category)


def assess(text: str, language: str | None = None) -> Assessment | None:
    """Return the rule engine's view of a message, or None if it cannot run."""
    try:
        result = safe_triage(text or "", language=language or "en")
    except Exception as exc:  # noqa: BLE001 - a broken engine must not block triage
        logger.error("rule engine failed with %s", type(exc).__name__)
        return None
    return Assessment(
        severity=result.severity.rank,
        category=_category(result),
        confident=result.confidence == "high",
        external_only=result.external_only,
        human_review=result.human_review,
        flags=[FLAG_PREFIX + rule for rule in result.matched_rules],
    )
