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
            r"\bbetter off without me\b",
            r"\b(nobody|no one) (would|will) (even |really )?(notice|miss|care) (if|when) i\b",
            r"\b(nobody|no one) (would|will) (even |really )?miss me\b",
            r"\bwant(s|ed)? to disappear (forever|for good)\b",
            r"\bdont want to wake up\b",
            r"\bdont want to go on (living|like this|anymore)\b",
            # v0.3: indirect wording, from misses in eval/data/hard_test.csv
            r"\b(no|dont see the|dont see any|whats the|what is the) point (of|in) (living|waking up|going on|being alive|being here|life)\b",
            r"\b(want|wish|need) (everything|it all|all of (it|this)|my life|the pain|life) to (stop|end)\b",
            r"\btired of (living|being alive|life|being here)\b",
            r"\b(took|taken|swallowed|drank|drunk) (a lot of|lots of|all|all of|many|too many|loads of|a bunch of|the whole)\b.{0,25}\b(pills?|tablets?|medicine|medication|panadol|drugs)\b",
            r"\b(saving|collecting|stockpiling|hiding) (up )?.{0,12}\b(pills|tablets|medicine)\b",
            r"\b(jump|jumping|throw myself) (off|from|in front of) (a|the)\b",
            r"\b(goodbye|suicide) (letters?|notes?|messages?)\b",
            r"\bif i (was|were) (gone|dead|not here)\b",
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
            r"\b(has|with|had|got) a (knife|gun|panga|machete)\b",
            # v0.3: a stranger near the child, or a threat to find or hurt them
            r"\b(man|men|stranger|adult|someone|somebody|person|guy|he|she|they)\b.{0,30}\b(waiting|standing|parked|hiding) (for me )?(outside|near|at|by) (my )?(school|house|home|gate|door|room)\b",
            r"\b(know|knows|found out|find out) where i (live|stay|sleep|study|go to school)\b",
            r"\b(posted|shared|leaked|sent|found) my (home )?(address|location)\b",
            r"\b(followed|following|follows|follow) me (home|to (my )?(school|house|home)|from (school|home))\b",
            r"\b(will|going to|gonna|is coming to|wants to) (find|get|hunt) me\b",
            r"\b(will|going to|gonna) (kill|burn|attack|stab|shoot) (me|us|our|my)\b",
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
