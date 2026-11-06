"""Referral router: which partners get a case, and the rules that decide it.

Rules (Guideline §4, plan §4.7):
- An adult in charge (parent, teacher, guardian, authority) as the alleged person
  means external routes only. School and home routes are always skipped.
- The school focal person is used only when the child chose it.
- Severity 4 always includes the helpline and police.
"""
from django.utils import timezone

from core.harm import picks
from core.models import Case, Partner, Referral

EXTERNAL_ONLY_ROLES = {"authority", "parent", "teacher", "guardian"}
AUTHORITY_ROUTE = ["sauti_116", "ucc", "counsellor", "police_cfpu"]
EMERGENCY_ROUTE = ["sauti_116", "police_cfpu"]
# Pick routes that are internal actions, not partners.
NOT_PARTNERS = {"human_responder", "companion", "trusted_adult_guide"}
ESCALATION_ORDER = ["sauti_116", "counsellor", "police_cfpu", "ucc"]


def plan_routes(case):
    """Return (partners, note). The note says which rule decided the route."""
    if case.alleged_role in EXTERNAL_ONLY_ROLES:
        slugs = list(AUTHORITY_ROUTE)
        note = "Adult in charge is the alleged person: external routes only, school and home routes skipped."
    else:
        pick = picks().get(case.pick or "")
        slugs = []
        for route in (pick["routes"] if pick else []):
            if route in NOT_PARTNERS:
                continue
            if route == "school_focal_if_child_chooses":
                if "child_chose_school" in (case.flags or []):
                    slugs.append("school_focal")
                continue
            slugs.append(route)
        note = f"Routed by the child's pick ({pick['short_en']})." if pick else "No pick: routed by severity."
        if not slugs:
            slugs = ["counsellor"]
    if case.severity >= 4:
        slugs = EMERGENCY_ROUTE + [s for s in slugs if s not in EMERGENCY_ROUTE]
        note += " Severity 4: helpline and police added."
    partners = {p.slug: p for p in Partner.objects.filter(slug__in=slugs)}
    ordered = [partners[s] for s in dict.fromkeys(slugs) if s in partners]
    if case.district:
        ordered = [p for p in ordered if not p.districts or case.district in p.districts or case.severity >= 4]
    return ordered, note


def payload(case):
    """What a partner receives. No reporter identity, ever."""
    return {
        "case_code": case.code,
        "severity": case.severity,
        "category": case.category,
        "pick": case.pick,
        "alleged_role": case.alleged_role,
        "language": case.language,
        "district": case.district,
        "flags": case.flags,
        "summary": case.summary,
        "contact": "Through Habari case officer only",
    }


def send_referrals(case, partners=None, now=None):
    """Create and deliver referrals. Skips partners that already have one. Returns new referrals."""
    from partners_mock import mock  # demo partners; a real deployment sends over each partner's channel

    now = now or timezone.now()
    if partners is None:
        partners, note = plan_routes(case)
        if note and case.routing_note != note:
            case.routing_note = note
            case.save(update_fields=["routing_note"])
    existing = set(case.referrals.values_list("partner_id", flat=True))
    created = []
    for p in partners:
        if p.id in existing:
            continue
        ref = Referral.objects.create(case=case, partner=p, payload=payload(case), sent_at=now)
        mock.deliver(ref, now)
        created.append(ref)
    if created:
        _advance(case, Case.Status.REFERRED, now)
    return created


# Statuses a referral may move a case on from. Later ones (in progress, resolved,
# closed) are set by people and are never moved back.
_BEFORE_REFERRED = {"received", "triaged", "assigned"}


def _advance(case, new_status, now):
    """Move the case forward to new_status, telling the child if the words change."""
    from core import followup

    case.refresh_from_db(fields=["status"])
    allowed = _BEFORE_REFERRED | ({"referred"} if new_status == Case.Status.ACKNOWLEDGED else set())
    if case.status in allowed:
        followup.set_status(case, new_status, now=now)


def escalate_second_partner(case, now=None):
    """Refer to the next partner not yet used. Authority cases never go to school."""
    used = set(case.referrals.values_list("partner__slug", flat=True))
    planned = [p.slug for p in plan_routes(case)[0]]
    for slug in planned + ESCALATION_ORDER:
        if slug in used or slug == "school_focal":
            continue
        partner = Partner.objects.filter(slug=slug).first()
        if partner:
            return send_referrals(case, partners=[partner], now=now)[0]
    return None


def acknowledge_referral(ref, now=None):
    now = now or timezone.now()
    if ref.ack_at:
        return ref
    ref.ack_at, ref.status = now, "acknowledged"
    ref.save(update_fields=["ack_at", "status"])
    case = ref.case
    if not case.ack_at:
        case.ack_at = now
        case.save(update_fields=["ack_at"])
    _advance(case, Case.Status.ACKNOWLEDGED, now)
    return ref
