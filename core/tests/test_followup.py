import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from channels.gateway import get_reporter
from core import followup, sla
from core.models import Case, Conversation, OutboundSMS, SLAEvent
from core.tests.helpers import after, make_case, seed

PHONE = "+256700000001"
CHECKIN_SECONDS = 4320 * 60 / 180  # 3 days in SLA time at scale 180 = 24 real minutes


@override_settings(SLA_TIME_SCALE=180)
class StatusUpdateTests(TestCase):
    def setUp(self):
        seed()

    def test_status_change_texts_the_child_in_plain_words(self):
        c = make_case()
        followup.set_status(c, Case.Status.REFERRED)
        sms = OutboundSMS.objects.get()
        self.assertIn("A helper is working on your report", sms.text)
        self.assertIn(c.code, sms.text)
        self.assertTrue(c.messages.filter(direction="out").exists())

    def test_same_words_are_not_sent_twice(self):
        c = make_case()
        followup.set_status(c, Case.Status.REFERRED)
        followup.set_status(c, Case.Status.ACKNOWLEDGED)  # same child-facing words
        self.assertEqual(OutboundSMS.objects.count(), 1)

    def test_no_message_after_the_child_sent_stop(self):
        c = make_case()
        r = c.reporter
        r.opted_out = True
        r.save()
        followup.set_status(c, Case.Status.REFERRED)
        self.assertEqual(OutboundSMS.objects.count(), 0)

    @override_settings(TELEGRAM_TOKEN="test-token")
    def test_telegram_child_is_messaged_through_the_bot(self):
        c = make_case(channel="telegram", sender="tg:42")
        with patch("channels.telegram.TelegramBot.call") as call:
            followup.set_status(c, Case.Status.REFERRED)
        method, = call.call_args.args
        self.assertEqual(method, "sendMessage")
        self.assertEqual(call.call_args.kwargs["chat_id"], 42)

    def test_web_child_sees_updates_on_the_status_page_only(self):
        c = make_case(channel="web", sender="web-abc")
        followup.set_status(c, Case.Status.REFERRED)
        self.assertEqual(OutboundSMS.objects.count(), 0)
        self.assertContains(self.client.get(f"/status/{c.code}"), "A helper is working on your report")


@override_settings(SLA_TIME_SCALE=180)
class SafetyCheckInTests(TestCase):
    def setUp(self):
        seed()
        self.t0 = timezone.now()

    def send(self, text):
        body = {"sender_id": PHONE, "text": text}
        return self.client.post("/api/channel/sms", json.dumps(body), content_type="application/json").json()

    def resolved_case(self):
        c = make_case(severity=3, ack_at=self.t0, first_response_at=self.t0)
        followup.set_status(c, Case.Status.RESOLVED, now=self.t0)
        return Case.objects.get(pk=c.pk)

    def test_check_in_is_sent_three_days_after_resolution(self):
        c = self.resolved_case()
        followup.process_due(after(self.t0, CHECKIN_SECONDS - 5))
        self.assertNotIn("Are you safe", OutboundSMS.objects.last().text)
        followup.process_due(after(self.t0, CHECKIN_SECONDS + 1))
        self.assertIn("Are you safe", OutboundSMS.objects.last().text)
        self.assertEqual(Case.objects.get(pk=c.pk).status, Case.Status.SAFETY_CHECK)

    def test_safe_answer_then_rating(self):
        c = self.resolved_case()
        followup.process_due(after(self.t0, CHECKIN_SECONDS + 1))
        self.assertIn("How did we do", self.send("1")["reply_text"])
        self.send("1")
        self.assertEqual(Case.objects.get(pk=c.pk).rating, "good")

    def test_not_safe_answer_reopens_the_case(self):
        c = self.resolved_case()
        followup.process_due(after(self.t0, CHECKIN_SECONDS + 1))
        self.send("2")
        c.refresh_from_db()
        self.assertEqual(c.clock_cycle, 1)
        self.assertGreaterEqual(c.severity, 3)
        self.assertIn("child_not_safe", c.flags)
        self.assertNotIn(c.status, (Case.Status.RESOLVED, Case.Status.SAFETY_CHECK))

    def test_one_gentle_follow_up_then_silence_and_never_auto_closed(self):
        c = self.resolved_case()
        for k in (1, 2, 3, 4):
            followup.process_due(after(self.t0, k * CHECKIN_SECONDS + 1))
        texts = list(OutboundSMS.objects.values_list("text", flat=True))
        self.assertEqual(sum("are you safe" in t.lower() for t in texts), 2)
        self.assertEqual(Case.objects.get(pk=c.pk).status, Case.Status.SAFETY_CHECK)


@override_settings(SLA_TIME_SCALE=180)
class ReopenAndRaiseTests(TestCase):
    def setUp(self):
        seed()

    def send(self, text):
        body = {"sender_id": PHONE, "text": text}
        return self.client.post("/api/channel/sms", json.dumps(body), content_type="application/json").json()

    def report(self, pick, text):
        self.send("HELP")
        self.send(pick)
        return Case.objects.get(code=self.send(text)["case_code"])

    def test_t3_7_new_information_reopens_a_closed_case(self):
        c = self.report("2", "he wants my pictures")
        followup.set_status(c, Case.Status.CLOSED, reason="resolved")
        self.send("he is back and messaging again")
        c.refresh_from_db()
        self.assertNotIn(c.status, (Case.Status.CLOSED,))
        self.assertIsNone(c.closed_at)
        self.assertEqual(c.clock_cycle, 1)
        sla.check(c, after(c.clock_started_at, 21))
        self.assertTrue(c.sla_events.filter(kind="ack_reminder", clock_cycle=1).exists())

    def test_t3_8_level_4_phrase_raises_severity_and_resets_clock(self):
        c = self.report("4", "they call me names")
        self.send("now i want to die")
        c.refresh_from_db()
        self.assertEqual(c.severity, 4)
        self.assertEqual(c.clock_cycle, 1)
        self.assertTrue(SLAEvent.objects.filter(case=c, kind="severity_raised").exists())
        sla.check(c, after(c.clock_started_at, 6))
        self.assertTrue(c.sla_events.filter(kind="page_on_call").exists())


class VaultTests(TestCase):
    def test_telegram_chat_id_is_kept_in_the_vault_for_follow_ups(self):
        rep = get_reporter("telegram", "tg:42", None)
        self.assertEqual(rep.vault.raw_contact, "tg:42")
