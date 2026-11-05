"""U-Report style polls: short questions to children who chose to JOIN.

Answers are counted by district. A district with fewer than HEATMAP_MIN answers
shows "fewer than N" so no child can be singled out.
"""
from collections import defaultdict

from django.conf import settings
from django.utils import timezone

from core.models import Conversation, Reporter, ReporterVault
from polls.models import PollResponse


def poll_text(poll):
    opts = " ".join(f"{i} {o}" for i, o in enumerate(poll.options, start=1))
    return f"Habari: {poll.question} Reply {opts}"


def _deliver(reporter, poll):
    text = poll_text(poll)
    if reporter.channel in ("sms", "ussd"):
        from channels.sms import send_sms
        return send_sms(reporter, text) is not None
    if reporter.channel == "telegram" and settings.TELEGRAM_TOKEN:
        vault = ReporterVault.objects.filter(reporter=reporter).first()
        if not (vault and vault.raw_contact.startswith("tg:")):
            return False
        from channels.telegram import TelegramBot
        keyboard = {"inline_keyboard": [[{"text": f"{i}. {o}", "callback_data": str(i)}]
                                        for i, o in enumerate(poll.options, start=1)]}
        try:
            TelegramBot(settings.TELEGRAM_TOKEN).call("sendMessage", chat_id=int(vault.raw_contact[3:]),
                                                      text=text, reply_markup=keyboard)
        except Exception:
            return False
        return True
    return False  # web, extension and Siri have no address to send to


def send_poll(poll):
    sent = 0
    for reporter in Reporter.objects.filter(poll_opt_in=True, opted_out=False):
        if not _deliver(reporter, poll):
            continue
        conv = reporter.conversations.filter(channel=reporter.channel).order_by("-updated_at").first() \
            or Conversation(reporter=reporter, channel=reporter.channel)
        conv.state, conv.draft = "POLL", {"poll": poll.id}
        conv.save()
        sent += 1
    poll.last_sent_at = timezone.now()
    poll.save(update_fields=["last_sent_at"])
    return sent


def record_answer(poll, reporter, answer):
    PollResponse.objects.update_or_create(poll=poll, reporter=reporter,
                                          defaults={"answer": answer, "district": reporter.district})


def results(poll):
    minimum = settings.HEATMAP_MIN
    by_district = defaultdict(lambda: defaultdict(int))
    for r in poll.responses.all():
        by_district[r.district or "Unknown"][r.answer] += 1
    rows = []
    for district, answers in sorted(by_district.items()):
        total = sum(answers.values())
        hidden = total < minimum
        rows.append({"district": district, "hidden": hidden, "total": None if hidden else total,
                     "answers": None if hidden else {o: answers.get(o, 0) for o in poll.options}})
    return rows
