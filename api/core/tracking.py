"""What a child may see about their own case: where it is, how long it has taken, and messages meant for them.

Never includes what they reported, who is handling it, the severity or any partner's name.
"""
from django.utils import timezone

from core.harm import sla_rules
from core.messages import _messages
from core.models import Case

STEPS = (
    ("received", "Report received", "We got your report."),
    ("sorted", "Checked for urgency", "We looked at how urgent it is."),
    ("helper", "A helper has it", "A trained helper is reading what you told us."),
    ("help", "Getting you help", "People who can help you, like a child protection partner, have been asked."),
    ("safe", "Making sure you are safe", "We will check that you are safe."),
    ("closed", "Closed", "Your report is closed. You can come back any time."),
)
# How far along each status is, as an index into STEPS.
REACHED = {
    "received": 0, "triaged": 1, "assigned": 2, "referred": 3, "acknowledged": 3, "in_progress": 3,
    "resolved": 4, "safety_check": 4, "closed": 5, "closed_unfounded": 5, "closed_child_stop": 5,
}
CLOSED_STATUSES = {"closed", "closed_unfounded", "closed_child_stop"}
MESSAGES_SHOWN = 5


def human(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "less than a minute"
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 24:
        left = minutes % 60
        return f"{hours} hour{'s' if hours != 1 else ''}" + (f" {left} min" if left else "")
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''}"


def _goal(case) -> str:
    """The time we aim for before a person sees the report. A goal, not a promise."""
    minutes = sla_rules().get(case.severity, {}).get("ack")
    if not minutes or case.ack_at or case.status in CLOSED_STATUSES:
        return ""
    return f"Our goal is that a person sees your report within {human(minutes * 60)}."


def track(case, now=None) -> dict:
    now = now or timezone.now()
    reached = REACHED.get(case.status, 0)
    closed = case.status in CLOSED_STATUSES
    first_referral = case.referrals.order_by("sent_at").first()
    times = [case.created_at, case.triaged_at, case.ack_at, first_referral.sent_at if first_referral else None,
             case.resolved_at, case.closed_at]
    steps = []
    for index, (key, title, detail) in enumerate(STEPS):
        # The first two steps are automatic, so they are finished once reached. After that a person is working on the step.
        if closed or index < reached or (index <= 1 and index <= reached):
            state = "done"
        elif index == reached or (reached <= 1 and index == reached + 1):
            state = "current"
        else:
            state = "todo"
        # A closed case never needed the steps it skipped.
        if closed and state == "todo":
            state = "skipped"
        if closed and key == "help" and not first_referral:
            state = "skipped"
        steps.append({"key": key, "title": title, "detail": detail, "state": state,
                      "at": times[index].isoformat() if times[index] and state == "done" else None})
    end = case.closed_at if closed and case.closed_at else now
    outgoing = list(case.messages.filter(direction="out").order_by("-created_at")[:MESSAGES_SHOWN])
    return {
        "code": case.code,
        "closed": closed,
        "headline": _messages("en")["status"][case.status],
        "steps": steps,
        "opened_at": case.created_at.isoformat(),
        "closed_at": case.closed_at.isoformat() if closed and case.closed_at else None,
        "took": human((end - case.created_at).total_seconds()),
        "goal": _goal(case),
        "messages": [{"text": m.text, "at": m.created_at.isoformat()} for m in reversed(outgoing)],
    }
