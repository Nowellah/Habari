"""Duplicate and repeat-offender finder (Guideline M8, plan F26).

Strong links: two cases share a handle, phone number or link. Identifiers are
stored as HMAC hashes, so the table never holds the raw handle or number, but
the same offender still matches after changing accounts on another case.

Weak links: similar wording (character 4-gram cosine). Works across code-mixed
text with no model. A multilingual embedding model can replace it later.
"""
import hashlib
import hmac
import math
import re
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.models import Case, CaseIdentifier

SIMILAR_AT = 0.55
LOOKBACK_DAYS = 90
KIND_NAMES = {"handle": "same handle", "phone": "same phone number", "url": "same link"}


def _norm(kind, value):
    value = value.strip().lower()
    if kind == "phone":
        digits = re.sub(r"\D", "", value)
        return "+256" + digits[1:] if digits.startswith("0") else "+" + digits
    if kind == "handle":
        return "@" + value.lstrip("@")
    return value.rstrip("/")


def _hash(kind, value):
    key = f"id:{kind}:{_norm(kind, value)}"
    return hmac.new(settings.HMAC_SECRET.encode(), key.encode(), hashlib.sha256).hexdigest()


def _identifiers(case):
    e = case.entities or {}
    found = [("handle", h) for h in e.get("handles", [])] + [("phone", p) for p in e.get("phones", [])] \
        + [("url", u) for u in e.get("urls", [])]
    for ev in case.evidence.filter(kind__in=["handle", "url"]):
        found.append((ev.kind, ev.value))
    return {(kind, _hash(kind, value)) for kind, value in found if value}


def index_case(case):
    for kind, hashed in _identifiers(case):
        CaseIdentifier.objects.get_or_create(case=case, kind=kind, hashed=hashed)


def _grams(text):
    words = re.sub(r"[^\w\s]", " ", (text or "").lower()).split()
    grams = Counter()
    for w in words:
        w = f" {w} "
        for i in range(max(1, len(w) - 3)):
            grams[w[i:i + 4]] += 1
    return grams


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def _text(case):
    return " ".join(case.messages.filter(direction="in").values_list("text", flat=True))


def linked_cases(case, limit=5):
    links = {}
    mine = CaseIdentifier.objects.filter(case=case)
    for other in CaseIdentifier.objects.filter(hashed__in=mine.values("hashed")).exclude(case=case) \
            .select_related("case"):
        entry = links.setdefault(other.case_id, {"case": other.case, "strength": "strong", "reasons": set()})
        entry["reasons"].add(KIND_NAMES.get(other.kind, "same identifier"))

    since = timezone.now() - timedelta(days=LOOKBACK_DAYS)
    my_grams = _grams(_text(case))
    for other in Case.objects.filter(created_at__gte=since).exclude(pk=case.pk).exclude(pk__in=links)[:500]:
        score = _cosine(my_grams, _grams(_text(other)))
        if score >= SIMILAR_AT:
            links[other.pk] = {"case": other, "strength": "weak", "reasons": {f"similar wording {score:.2f}"}}

    ordered = sorted(links.values(), key=lambda l: (l["strength"] != "strong", l["case"].created_at))
    return [{"case": l["case"], "strength": l["strength"], "reason": ", ".join(sorted(l["reasons"]))}
            for l in ordered[:limit]]
