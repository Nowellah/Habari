"""Follow-up loop: from report to closure (Guideline §18).

- Every status change the child would notice is sent back on their channel in
  plain words (SMS, Telegram) or shown on the status page (web).
- Three days (SLA time) after Resolved, the child is asked "Are you safe now?".
  No reply gets one gentle follow-up. Silence never closes a case.
- Only a person closes a case, with a reason.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.messages import msg, status_words
from core.models import Case, Conversation, Message, ReporterVault

CHECKIN_AFTER_MINUTES = 3 * 24 * 60  # SLA minutes
MAX_CHECKINS = 2
CLOSED = {Case.Status.CLOSED, Case.Status.CLOSED_UNFOUNDED, Case.Status.CLOSED_CHILD_STOP}


def _real(sla_minutes):
    return timedelta(minutes=sla_minutes / max(float(settings.SLA_TIME_SCALE), 0.0001))


def send_to_child(case, text):
    """Record the message on the case and deliver it on the child's channel if we can."""
    Message.objects.create(case=case, direction="out", text=text, channel=case.channel)
    reporter = case.reporter
    if reporter is None or reporter.opted_out:
        return
    if case.channel in ("sms", "ussd"):
        from channels.sms import send_sms
        send_sms(reporter, text)
    elif case.channel == "whatsapp":
        vault = ReporterVault.objects.filter(reporter=reporter).first()
        if vault:
            from channels.whatsapp import send_whatsapp
            send_whatsapp(reporter, vault.raw_contact.lstrip("+"), text)
    elif case.channel == "telegram" and settings.TELEGRAM_TOKEN:
        vault = ReporterVault.objects.filter(reporter=reporter).first()
        if vault and vault.raw_contact.startswith("tg:"):
            from channels.telegram import TelegramBot
            try:
                TelegramBot(settings.TELEGRAM_TOKEN).call("sendMessage", chat_id=int(vault.raw_contact[3:]), text=text)
            except Exception:
                pass  # the message is still on the case and the status page
    # web, extension, siri: the child sees it on /status/<code>


def set_status(case, new_status, now=None, reason=""):
    now = now or timezone.now()
    before = status_words(case)
    case.status = new_status
    fields = ["status"]
    if new_status == Case.Status.RESOLVED:
        case.resolved_at, case.checkin_due_at, case.checkin_count = now, now + _real(CHECKIN_AFTER_MINUTES), 0
        fields += ["resolved_at", "checkin_due_at", "checkin_count"]
    if new_status in CLOSED:
        case.closed_at, case.close_reason, case.checkin_due_at = now, reason, None
        fields += ["closed_at", "close_reason", "checkin_due_at"]
    case.save(update_fields=fields)
    after = status_words(case)
    if after != before:
        send_to_child(case, msg("status_update", code=case.code, words=after.split(": ", 1)[1]))


def _set_conversation(case, state):
    if case.reporter is None:
        return
    conv = case.reporter.conversations.filter(channel=case.channel).order_by("-updated_at").first()
    if conv is None:
        conv = Conversation(reporter=case.reporter, channel=case.channel)
    conv.state, conv.case = state, case
    conv.save()


def process_due(now=None):
    """Send safety check-ins that are due."""
    now = now or timezone.now()
    due = Case.objects.filter(status__in=[Case.Status.RESOLVED, Case.Status.SAFETY_CHECK],
                              checkin_due_at__lte=now, checkin_count__lt=MAX_CHECKINS)
    for case in due:
        first = case.checkin_count == 0
        send_to_child(case, msg("checkin" if first else "checkin_again", code=case.code))
        case.checkin_count += 1
        case.status = Case.Status.SAFETY_CHECK
        case.checkin_due_at = now + _real(CHECKIN_AFTER_MINUTES) if case.checkin_count < MAX_CHECKINS else None
        case.save(update_fields=["checkin_count", "status", "checkin_due_at"])
        _set_conversation(case, "CHECKIN")


def reopen(case, why, now=None):
    """New information or 'not safe': the case goes back to the queue on a fresh clock."""
    from core import sla

    now = now or timezone.now()
    case.status = Case.Status.ASSIGNED if case.assigned_officer else Case.Status.RECEIVED
    case.closed_at, case.close_reason, case.checkin_due_at = None, "", None
    case.save(update_fields=["status", "closed_at", "close_reason", "checkin_due_at"])
    sla.reset_clock(case, f"reopened: {why}", now)
