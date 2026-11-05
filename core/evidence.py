"""Evidence vault with a hash chain: editing an old entry breaks every later hash."""
import hashlib

from django.db import transaction

from core.models import Case, Evidence

ZERO = "0" * 64


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _chain(prev: str, kind: str, value_hash: str) -> str:
    return _sha(f"{prev}|{kind}|{value_hash}")


def add_evidence(case: Case, kind: str, value: str) -> Evidence:
    with transaction.atomic():
        # Lock the case row so two entries added at once cannot share a prev_hash.
        Case.objects.select_for_update().filter(pk=case.pk).first()
        last = case.evidence.order_by("-id").first()
        prev = last.chain_hash if last else ZERO
        value_hash = _sha(value)
        return Evidence.objects.create(
            case=case, kind=kind, value=value, value_sha256=value_hash,
            prev_hash=prev, chain_hash=_chain(prev, kind, value_hash),
        )


def verify_chain(case: Case) -> bool:
    prev = ZERO
    for e in case.evidence.order_by("id"):
        value_hash = _sha(e.value)
        if e.value_sha256 != value_hash or e.prev_hash != prev or e.chain_hash != _chain(prev, e.kind, value_hash):
            return False
        prev = e.chain_hash
    return True
