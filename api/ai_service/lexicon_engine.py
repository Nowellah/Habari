"""Keyword lexicon engine. Plain Python, no Django, shared by the web app and the AI service."""
import re
from functools import lru_cache
from pathlib import Path

import yaml

LEXICON_PATH = Path(__file__).resolve().parent / "lexicon.yaml"

# Flags that show harm. An adult in charge only changes the case (role, category,
# referral) when one of these is also present.
AUTHORITY_HARM_FLAGS = frozenset({
    "harm_by_person", "threat", "imminent_danger", "sextortion", "grooming",
    "self_harm_incitement", "bullying", "risk_context",
})


def authority_harm(flags) -> bool:
    """True when an adult in charge is named together with a sign of harm."""
    return "authority" in flags and any(f in AUTHORITY_HARM_FLAGS for f in flags)


@lru_cache
def load(path: str = str(LEXICON_PATH)) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf8"))


def normalise_text(text: str, lex: dict | None = None) -> str:
    lex = lex or load()
    words = re.sub(r"[^\w\s]", " ", (text or "").lower()).split()
    shorthand = lex.get("shorthand", {})
    return " ".join(shorthand.get(w, w) for w in words)


def _contains(norm_text: str, term: str, lex: dict) -> bool:
    # Whole words only, so "bet" does not match "better".
    return re.search(rf"(?<!\w){re.escape(normalise_text(term, lex))}(?!\w)", norm_text) is not None


def match(text: str, lex: dict | None = None) -> tuple[list[str], int]:
    """Return (flags, floor severity) for a message. Floor 0 means no floor."""
    lex = lex or load()
    norm = normalise_text(text, lex)
    flags, floor = [], 0
    for name, spec in lex["flags"].items():
        terms = [t for lang_terms in spec["terms"].values() for t in lang_terms]
        if any(_contains(norm, t, lex) for t in terms):
            flags.append(name)
            floor = max(floor, spec.get("floor", 0))
    for combo in lex.get("combinations", []):
        if all(f in flags for f in combo["all_of"]):
            floor = max(floor, combo["floor"])
    return flags, floor


def language_hits(text: str, lex: dict | None = None) -> dict[str, int]:
    """Count marker words (1 point) and lexicon terms (2 points) per language."""
    lex = lex or load()
    norm = normalise_text(text, lex)
    tokens = norm.split()
    hits = {}
    for lang, markers in lex.get("language_markers", {}).items():
        marker_set = {normalise_text(str(m), lex) for m in markers}
        score = sum(1 for t in tokens if t in marker_set)
        for spec in lex["flags"].values():
            score += 2 * sum(1 for t in spec["terms"].get(lang, []) if _contains(norm, t, lex))
        hits[lang] = score
    return hits
