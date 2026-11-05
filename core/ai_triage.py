"""Background AI triage. The child's reply never waits for this.

If the AI service is down, the case is raised to at least severity 3 so a human
looks at it soon (fail-safe: no report is left sitting at a low level unread).
"""
import threading

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from core import ai_client
from core.models import Case

AI_DOWN_FLOOR = 3


def schedule(case_id: int):
    """Call after the reply is decided. Runs after the database commit."""
    def start():
        if settings.AI_TRIAGE_INLINE:
            run(case_id)
        else:
            threading.Thread(target=_run_in_thread, args=(case_id,), daemon=True).start()
    transaction.on_commit(start)


def _run_in_thread(case_id):
    try:
        run(case_id)
    finally:
        close_old_connections()


def run(case_id: int):
    case = Case.objects.filter(pk=case_id).first()
    if not case:
        return
    incoming = list(case.messages.filter(direction="in").order_by("created_at"))
    text = " ".join(m.text for m in incoming)
    result = ai_client.triage(text, case.pick, case.language or None)
    apply(case_id, result)
    if result is not None and incoming:
        synthesis = ai_client.summarise([{"text": m.text, "at": m.created_at.isoformat()} for m in incoming])
        if synthesis:
            Case.objects.filter(pk=case_id).update(summary=synthesis["summary"][:2000],
                                                   entities=synthesis.get("entities") or {})
            from core import linking
            linking.index_case(Case.objects.get(pk=case_id))


def apply(case_id: int, result: dict | None):
    from core import sla

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)
        was = case.severity
        flags = set(case.flags)
        if result is None:
            case.severity = max(case.severity, AI_DOWN_FLOOR)
            flags.add("ai_unavailable")
            case.triage_source = "rules_ai_down"
        else:
            case.severity = max(case.severity, int(result.get("severity") or 1))  # never lower
            flags |= set(result.get("flags") or [])
            if result.get("category") and result["category"] != "unclear":
                case.category = result["category"]
            if result.get("role") and not case.alleged_role:
                case.alleged_role = result["role"]
            if not case.language and result.get("language") not in (None, "", "unknown") \
                    and (result.get("language_confidence") or 0) >= 0.6:
                case.language = result["language"]
                case.language_conf = result.get("language_confidence")
            case.triage_source = "ai"
        case.flags = sorted(flags)
        case.triaged_at = timezone.now()
        if case.status == Case.Status.RECEIVED:
            case.status = Case.Status.TRIAGED
        case.save()
        if case.severity > was:
            sla.reset_clock(case, f"AI raised severity {was} -> {case.severity}")
            sla.once(case, "severity_raised", f"{was} -> {case.severity}: {case.triage_source}")
    after_triage(case_id)


def after_triage(case_id: int):
    """Assign an officer; severity 4 is referred to the helpline and police at once."""
    from core import allocation, router

    case = Case.objects.get(pk=case_id)
    if case.assigned_officer is None:
        allocation.allocate(case)
    if case.severity >= 4:
        router.send_referrals(case)
