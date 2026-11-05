"""Dependency-free fast path that detects immediate danger.

This module imports nothing outside the standard library so that it keeps
working when every other part of the service fails. Matching is deliberately
broad: a false alarm costs a human review, a miss can cost a life. Phrases
are matched even when negated, because a person writing that they do not want
to live must never be missed.
"""
import re
import unicodedata
from typing import NamedTuple

_APOSTROPHES = dict.fromkeys(map(ord, "'’‘`´"), None)
_ZERO_WIDTH = re.compile("[​-‏⁠﻿]")
_REPEATS = re.compile(r"(.)\1{2,}")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, drop apostrophes and zero-width characters, squeeze repeats and spaces."""
    value = unicodedata.normalize("NFKC", text).lower().translate(_APOSTROPHES)
    value = _ZERO_WIDTH.sub("", value)
    value = _REPEATS.sub(r"\1\1", value)
    return _SPACES.sub(" ", value).strip()


class DangerMatch(NamedTuple):
    rule_id: str
    category: str


_RULES = (
    (
        "danger_self_harm",
        "self_harm",
        (
            r"\bkill(ing)? myself\b",
            r"\bend(ing)? (my|this) (own )?life\b",
            r"\bwant(ed|s)? to die\b",
            r"\bsuicid\w*",
            r"\bdont want to (live|be alive|exist|be here)\b",
            r"\b(hurt|harm|cut|hurting|harming|cutting) myself\b",
            r"\bbetter off dead\b",
            r"\bend it all\b",
            r"\bno (reason|point) (to|in) (live|living|going on)\b",
            r"\btake my own life\b",
            r"\bwish i (was|were) dead\b",
            r"\b(hang|poison|drown|shoot|stab) myself\b",
            r"\boverdos\w*",
            r"\bkms\b",
        ),
    ),
    (
        "danger_immediate",
        "immediate_danger",
        (
            r"\bkill (me|us)\b",
            r"\b(is|are) (hurting|beating|raping|choking|strangling|attacking|stabbing) me\b",
            r"\bim (in danger|being (attacked|abducted|kidnapped))\b",
            r"\b(in danger|unsafe) (now|right now)\b",
            r"\b(he|she|they|man|men|someone|stranger) (is |are |was )?(outside|at) my (door|window|room|house|gate)\b",
            r"\b(he|she|they) (is|are) coming (for|to get) me\b",
            r"\bcoming to (my house|get me|kill)\b",
            r"\blocked (me|us) (in|up)\b",
            r"\bhelp me now\b",
            r"\bsave me\b",
            r"\bsos\b",
            r"\b(has|with) a (knife|gun|panga)\b",
            "\U0001F198",
            "\U0001F6A8",
        ),
    ),
)

_COMPILED = tuple(
    (rule_id, category, tuple(re.compile(p) for p in patterns))
    for rule_id, category, patterns in _RULES
)


def detect_danger(normalized_text: str) -> list[DangerMatch]:
    """Return one match per danger rule that fires on already normalised text."""
    return [
        DangerMatch(rule_id, category)
        for rule_id, category, patterns in _COMPILED
        if any(p.search(normalized_text) for p in patterns)
    ]
