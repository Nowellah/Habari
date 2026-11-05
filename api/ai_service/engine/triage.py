"""Severity and category assessment for a child's message.

Rules can only raise severity. Nothing in this module lowers it, because only
a person may lower the severity of a case.
"""
import logging
from dataclasses import dataclass

from .danger import detect_danger, normalize
from .lexicon import (
    CATEGORY_PRIORITY,
    DEMAND_TERMS,
    GREETING,
    HARM_WORDS,
    HINT_SEVERITY,
    IMAGE_TERMS,
    LEXICON_RULES,
    PAYMENT_TERMS,
    TRUSTED_ROLE_TEXT,
    TRUSTED_ROLES_FROM_CONTEXT,
)
from .schemas import Category, Severity, TriageResult

logger = logging.getLogger("habari.ai")

_MIN_WORDS_FOR_UNCLEAR_ESCALATION = 3


@dataclass(frozen=True)
class _Signal:
    rule_id: str
    category: Category
    severity: Severity
    low_confidence: bool = False
    fallback: bool = False


def _text_signals(text: str) -> list[_Signal]:
    signals = [
        _Signal(hit.rule_id, Category(hit.category), Severity.S4)
        for hit in detect_danger(text)
    ]
    for rule in LEXICON_RULES:
        if rule.matches(text):
            signals.append(_Signal(rule.rule_id, rule.category, rule.severity, rule.weak))
    if IMAGE_TERMS.search(text) and PAYMENT_TERMS.search(text) and DEMAND_TERMS.search(text):
        # v0.3: S4, matching the case engine's sextortion + money + threat combination.
        signals.append(_Signal("sextortion_payment_demand", Category.SEXTORTION, Severity.S4))
    return signals


def _unmatched_signal(text: str, language: str) -> _Signal:
    """Policy for text no rule recognised: never treat unknown as safe."""
    if GREETING.match(text):
        return _Signal("greeting", Category.OTHER, Severity.S1, fallback=True)
    if language != "en":
        return _Signal("language_not_assessable", Category.OTHER, Severity.S3, low_confidence=True, fallback=True)
    if len(text.split()) >= _MIN_WORDS_FOR_UNCLEAR_ESCALATION:
        return _Signal("unclear_message", Category.OTHER, Severity.S2, low_confidence=True, fallback=True)
    return _Signal("short_message", Category.OTHER, Severity.S1, low_confidence=True, fallback=True)


def _best_signal(signals: list[_Signal]) -> _Signal:
    return min(
        signals,
        key=lambda s: (-s.severity.rank, CATEGORY_PRIORITY.index(s.category)),
    )


def triage(
    message: str,
    language: str = "en",
    happening_now: bool | None = None,
    alleged_role: str | None = None,
    category_hint: str | None = None,
) -> TriageResult:
    """Classify a message using the child's own selections and the text together."""
    text = normalize(message)
    signals = _text_signals(text)

    if category_hint and category_hint in HINT_SEVERITY:
        signals.append(
            _Signal(f"hint_{category_hint}", Category(category_hint), HINT_SEVERITY[category_hint])
        )

    if not signals:
        signals.append(_unmatched_signal(text, language))

    best = _best_signal(signals)
    severity = best.severity
    rules = [s.rule_id for s in signals]

    if happening_now and severity == Severity.S2:
        severity = Severity.S3
        rules.append("happening_now")

    external_only = False
    role_involved = alleged_role in TRUSTED_ROLES_FROM_CONTEXT or bool(TRUSTED_ROLE_TEXT.search(text))
    evidence_rank = max((s.severity.rank for s in signals if not s.fallback), default=0)
    if role_involved and (evidence_rank >= Severity.S2.rank or HARM_WORDS.search(text)):
        severity = Severity.from_rank(max(severity.rank, Severity.S3.rank))
        external_only = True
        rules.append("trusted_adult_involved")

    confident = any(not s.low_confidence for s in signals)
    danger = severity == Severity.S4
    return TriageResult(
        severity=severity,
        category=best.category,
        confidence="high" if confident else "low",
        matched_rules=list(dict.fromkeys(rules)),
        danger=danger,
        human_review=severity.rank >= Severity.S3.rank or not confident or external_only,
        external_only=external_only,
        needs_clarification=not danger and (not confident or "greeting" in rules),
    )


def safe_triage(message: str, **context) -> TriageResult:
    """Run triage and degrade safely: danger phrases still win, anything else becomes S3."""
    try:
        return triage(message, **context)
    except Exception as exc:  # noqa: BLE001 - the service must always answer
        logger.error("triage failed with %s", type(exc).__name__)
        try:
            hits = detect_danger(normalize(message))
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            return TriageResult(
                severity=Severity.S4,
                category=Category(hits[0].category),
                confidence="high",
                matched_rules=[h.rule_id for h in hits] + ["triage_degraded"],
                danger=True,
                human_review=True,
                external_only=False,
                needs_clarification=False,
            )
        return TriageResult(
            severity=Severity.S3,
            category=Category.OTHER,
            confidence="low",
            matched_rules=["triage_unavailable"],
            danger=False,
            human_review=True,
            external_only=False,
            needs_clarification=False,
        )
