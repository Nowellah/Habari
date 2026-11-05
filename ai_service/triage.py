"""Triage: lexicon rules first, then an optional zero-shot classifier on top.

Rules are the floor. A classifier can only raise severity, and only when it is
confident. If the classifier fails, the rules result stands.
"""
import json
from functools import lru_cache
from pathlib import Path

from ai_service import lexicon_engine
from ai_service.language import detect_language

HARM_PICKER = Path(__file__).resolve().parent.parent / "shared" / "harm_picker.json"

CATEGORIES = [
    "self_harm", "threats", "grooming", "sextortion", "exposure_by_authority",
    "cyberbullying", "impersonation", "inappropriate_content", "gambling_or_betting", "scam",
]
# Severity floor a confident classifier label implies.
CATEGORY_FLOOR = {
    "self_harm": 4, "threats": 3, "grooming": 3, "sextortion": 3, "exposure_by_authority": 3,
    "cyberbullying": 2, "impersonation": 2, "inappropriate_content": 1, "gambling_or_betting": 2, "scam": 2,
}
CLASSIFIER_MIN_SCORE = 0.7
PICK_DEFAULT_CATEGORY = {"1": "threats", "2": "sextortion", "3": "exposure_by_authority", "4": "cyberbullying", "5": "inappropriate_content"}


@lru_cache
def _pick_severity() -> dict:
    data = json.loads(HARM_PICKER.read_text(encoding="utf8"))
    return {p["id"]: p["default_severity"] for p in data["picks"]}


def _category_from_flags(flags, pick):
    if "self_harm" in flags:
        return "self_harm"
    if "imminent_danger" in flags:
        return "threats"
    if pick == "3":
        return "exposure_by_authority"
    if "sextortion" in flags:
        return "sextortion"
    if "threat" in flags:
        return "threats"
    if "gambling" in flags:
        return "gambling_or_betting"
    if "money_demand" in flags:
        return "scam"
    return PICK_DEFAULT_CATEGORY.get(pick or "", "unclear")


def _pick_for(category, flags):
    if category == "self_harm" or "imminent_danger" in flags:
        return "1"
    return {
        "threats": "4", "grooming": "2", "sextortion": "2", "exposure_by_authority": "3",
        "cyberbullying": "4", "impersonation": "4", "inappropriate_content": "5",
        "gambling_or_betting": "5", "scam": "5",
    }.get(category)


def triage(text: str, pick: str | None = None, language: str | None = None, classifier=None) -> dict:
    flags, floor = lexicon_engine.match(text)
    severity = max(_pick_severity().get(pick or "", 1), floor)
    category = _category_from_flags(flags, pick)
    harm_flags = [f for f in flags if f != "authority"]
    confidence = 0.85 if harm_flags else (0.5 if pick else 0.2)
    method = "rules"

    if classifier and text.strip():
        try:
            scores = classifier(text, CATEGORIES)
            label, score = max(scores.items(), key=lambda kv: kv[1])
            if score >= CLASSIFIER_MIN_SCORE:
                method = "rules+classifier"
                if CATEGORY_FLOOR.get(label, 0) > severity or category in ("unclear",) or not harm_flags:
                    category = label
                severity = max(severity, CATEGORY_FLOOR.get(label, 0))
                confidence = max(confidence, round(score, 2))
        except Exception:  # a broken model must never block or lower triage
            method = "rules (classifier failed)"

    lang = detect_language(text) if text.strip() else {"language": "unknown", "confidence": 0.0, "ask_language": True}
    return {
        "pick_suggestion": _pick_for(category, flags),
        "category": category,
        "severity": severity,
        "role": "authority" if ("authority" in flags or pick == "3") else "",
        "confidence": confidence,
        "flags": flags,
        "language": language or lang["language"],
        "language_confidence": 1.0 if language else lang["confidence"],
        "ask_language": False if language else lang["ask_language"],
        "method": method,
    }
