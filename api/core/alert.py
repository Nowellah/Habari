"""Escalation alerts: notify officers when a case needs urgent attention.

Called from ai_triage.after_triage() after every case is triaged.

Two alert paths:
  1. Email  — Django's built-in send_mail (console backend in dev,
               swap MAILERS to SMTP in production settings).
  2. SMS    — via channels.sms.send_sms (same path as all other outbound SMS).

Both paths are fire-and-forget: failures log a warning but never raise,
so the gateway response to the child is never blocked.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

from core.models import Case, Officer

logger = logging.getLogger(__name__)


def _on_call_officers():
    """Return on-call officers, or all officers if none are marked on-call."""
    qs = Officer.objects.filter(on_call=True).select_related("user")
    if not qs.exists():
        qs = Officer.objects.all().select_related("user")
    return list(qs)


def _officer_emails(officers):
    return [o.user.email for o in officers if o.user.email]


def _subject(case: Case) -> str:
    labels = {4: "DANGER", 3: "HIGH", 2: "MEDIUM", 1: "LOW"}
    return f"[Habari {labels.get(case.severity, case.severity)}] Case {case.code} needs attention"


def _body(case: Case, reason: str) -> str:
    base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    url = f"{base}/officer/case/{case.code}/" if base else f"/officer/case/{case.code}/"
    return "\n".join([
        f"Case {case.code} — {reason}",
        "",
        f"Severity : {case.severity} / 4",
        f"Category : {case.category or '—'}",
        f"Channel  : {case.channel}",
        f"Flags    : {', '.join(case.flags) or 'none'}",
        f"Status   : {case.get_status_display()}",
        f"Assigned : {case.assigned_officer.user.get_username() if case.assigned_officer else 'unassigned'}",
        "",
        f"Open case: {url}",
        "",
        f"Call {settings.HELPLINE_NUMBER} if the child is in immediate danger.",
    ])


def _sms_text(case: Case, reason: str) -> str:
    return (
        f"[Habari] Case {case.code} sev {case.severity}: {reason}. "
        f"Open dashboard. Call {settings.HELPLINE_NUMBER} if danger."
    )


def notify_officers(case: Case, reason: str = "new sensitive case") -> None:
    """Email (and optionally SMS) on-call officers. All exceptions are caught."""
    officers = _on_call_officers()
    if not officers:
        logger.warning("alert: no officers for case %s", case.code)
        return

    # Email
    emails = _officer_emails(officers)
    if emails:
        try:
            send_mail(
                subject=_subject(case),
                message=_body(case, reason),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "habari@localhost"),
                recipient_list=emails,
            )
            logger.info("alert: emailed %d officer(s) for case %s", len(emails), case.code)
        except Exception:
            logger.exception("alert: email failed for case %s", case.code)

    # SMS — uses the same send_sms path as all outbound SMS
    # Only fires if officers have phone-looking usernames (e.g. +256700000001)
    try:
        from channels.sms import send_sms
        for officer in officers:
            uname = officer.user.username
            if uname.startswith("+") or (uname.isdigit() and len(uname) >= 9):
                send_sms(None, _sms_text(case, reason), to_number=uname)
    except Exception:
        logger.exception("alert: SMS alert failed for case %s", case.code)


def maybe_escalate(case: Case, reason: str = "case triaged") -> None:
    """Alert officers for sev-3/4 or high-risk flag cases."""
    HIGH_RISK = {"threat", "sextortion", "self_harm", "danger"}
    if case.severity >= 3 or bool(HIGH_RISK & set(case.flags)):
        notify_officers(case, reason)
