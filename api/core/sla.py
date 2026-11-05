"""SLA clocks and automatic escalation (plan §8, Guideline §17).

Each case has a clock that starts at submission. Times are in "SLA minutes":
real minutes multiplied by SLA_TIME_SCALE, so a demo can run the whole chain fast.

| Situation                                  | Action                                         |
| No acknowledgement at 50% of the window    | Reminder to assigned officer and partners      |
| No acknowledgement at 100%                 | Reassign to next officer, notify supervisor    |
| No first response at 150% of response time | Escalate to head of unit and a second partner  |
| Severity 4, no response at 15 min          | Page on-call, re-show helpline, mark Critical  |
| Severity raised / case reopened            | Reset to the new clock (reset_clock)           |
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core import allocation, router
from core.harm import sla_rules
from core.messages import msg
from core.models import Case, Notification, Officer, SLAEvent

PAGE_AFTER = 15  # SLA minutes, severity 4
INACTIVE = [Case.Status.RESOLVED, Case.Status.SAFETY_CHECK, Case.Status.CLOSED,
            Case.Status.CLOSED_UNFOUNDED, Case.Status.CLOSED_CHILD_STOP]


def scale():
    return max(float(settings.SLA_TIME_SCALE), 0.0001)


def elapsed(case, now):
    """SLA minutes on the current clock."""
    return (now - case.clock_started_at).total_seconds() / 60 * scale()


def windows(case):
    rule = sla_rules()[max(1, min(4, case.severity))]
    return rule["ack"], rule["first_response"]


def once(case, kind, detail="", now=None):
    """Record an event once per case and clock cycle. Returns True the first time."""
    if SLAEvent.objects.filter(case=case, kind=kind, clock_cycle=case.clock_cycle).exists():
        return False
    SLAEvent.objects.create(case=case, kind=kind, clock_cycle=case.clock_cycle, detail=detail,
                            at=now or timezone.now())
    return True


def notify(case, audience, text, officer=None, now=None):
    Notification.objects.create(case=case, audience=audience, officer=officer, text=text,
                                created_at=now or timezone.now())


def reset_clock(case, reason, now=None):
    now = now or timezone.now()
    SLAEvent.objects.create(case=case, kind="clock_reset", clock_cycle=case.clock_cycle,
                            detail=f"{reason}; ack_at={case.ack_at}, first_response_at={case.first_response_at}", at=now)
    case.clock_started_at, case.clock_cycle = now, case.clock_cycle + 1
    case.ack_at = case.first_response_at = None
    case.save(update_fields=["clock_started_at", "clock_cycle", "ack_at", "first_response_at"])


def clock_state(case, now=None):
    """Colour and label for the officer dashboard."""
    now = now or timezone.now()
    if case.status in INACTIVE or case.first_response_at:
        return {"colour": "done", "pct": 0, "label": "Responded" if case.first_response_at else "Not running"}
    ack_w, resp_w = windows(case)
    window, what = (resp_w, "response") if case.ack_at else (ack_w, "ack")
    e = elapsed(case, now)
    pct = round(100 * e / window)
    colour = "green" if pct < 50 else ("amber" if pct < 100 else "red")
    left = window - e
    label = f"{what} due in {_fmt(left)}" if left > 0 else f"{what} overdue by {_fmt(-left)}"
    return {"colour": colour, "pct": pct, "label": label}


def _fmt(sla_minutes):
    m = int(sla_minutes)
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def check(case, now=None):
    """Apply the SLA rules to one case. Safe to call as often as you like."""
    from core import followup

    now = now or timezone.now()
    if case.status in INACTIVE or case.first_response_at:
        return
    ack_w, resp_w = windows(case)
    e = elapsed(case, now)
    officer = case.assigned_officer

    if not case.ack_at:
        if e >= ack_w * 0.5 and once(case, "ack_reminder", now=now):
            notify(case, "officer", f"Reminder: case {case.code} needs acknowledging.", officer, now)
            for ref in case.referrals.filter(ack_at__isnull=True):
                notify(case, "partner", f"Reminder to {ref.partner.name}: please acknowledge {case.code}.", now=now)
        if e >= ack_w and once(case, "ack_breach", now=now):
            new = allocation.reassign_next(case, "no acknowledgement in time")
            notify(case, "supervisor", f"Breach: case {case.code} was not acknowledged in time. "
                                       f"Reassigned to {new.user.get_username() if new else 'nobody available'}.",
                   now=now)
    if e >= resp_w * 1.5 and once(case, "escalate_head", now=now):
        notify(case, "supervisor", f"Escalated to head of unit: case {case.code} has no first response.", now=now)
        extra = router.escalate_second_partner(case, now=now)
        if extra:
            SLAEvent.objects.filter(case=case, kind="escalate_head", clock_cycle=case.clock_cycle) \
                .update(detail=f"second partner: {extra.partner.name}")
    if case.severity >= 4 and e >= PAGE_AFTER and once(case, "page_on_call", now=now):
        for o in Officer.objects.filter(on_call=True):
            notify(case, "on_call", f"PAGE: severity 4 case {case.code} has no response.", o, now)
        notify(case, "on_call", f"PAGE: severity 4 case {case.code} has no response.", now=now)
        with transaction.atomic():
            c = Case.objects.select_for_update().get(pk=case.pk)
            c.flags = sorted(set(c.flags) | {"critical"})
            c.save(update_fields=["flags"])
        case.flags = c.flags
        followup.send_to_child(case, msg("danger_again", code=case.code))


def tick(now=None):
    """One pass of the watcher: SLA rules, simulated partners, follow-ups."""
    from core import followup
    from partners_mock import mock

    now = now or timezone.now()
    mock.process_due(now)
    for case in Case.objects.exclude(status__in=INACTIVE).filter(first_response_at__isnull=True) \
            .select_related("assigned_officer__user"):
        check(case, now)
    followup.process_due(now)
