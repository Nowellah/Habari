import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from channels.gateway import get_reporter
from core.models import Case, OutboundSMS, Reporter
from core.tests.helpers import seed
from polls.models import Poll, PollResponse
from polls.service import results, send_poll


class PollFlowTests(TestCase):
    def setUp(self):
        self.poll = Poll.objects.create(question="Did anyone make you uncomfortable online this week?",
                                        options=["Yes", "No", "Skip"])

    def send(self, text, sender="+256700000001", channel="sms"):
        body = {"sender_id": sender, "text": text}
        return self.client.post(f"/api/channel/{channel}", json.dumps(body), content_type="application/json").json()

    def test_join_opts_in(self):
        out = self.send("JOIN")
        self.assertIn("short safety questions", out["reply_text"])
        self.assertTrue(Reporter.objects.get().poll_opt_in)

    def test_poll_goes_only_to_children_who_joined(self):
        self.send("JOIN")
        self.send("HELP", sender="+256700000002")
        sent = send_poll(self.poll)
        self.assertEqual(sent, 1)
        self.assertIn("uncomfortable online", OutboundSMS.objects.last().text)

    def test_stop_means_no_more_polls(self):
        self.send("JOIN")
        self.send("STOP")
        self.assertEqual(send_poll(self.poll), 0)

    @override_settings(TELEGRAM_TOKEN="t")
    def test_telegram_members_get_the_poll_with_buttons(self):
        self.send("JOIN", sender="tg:42", channel="telegram")
        with patch("channels.telegram.TelegramBot.call") as call:
            send_poll(self.poll)
        self.assertEqual(call.call_args.kwargs["chat_id"], 42)
        self.assertIn("reply_markup", call.call_args.kwargs)

    def test_yes_is_counted_and_opens_a_gentle_chat_but_no_case(self):
        self.send("JOIN")
        send_poll(self.poll)
        out = self.send("1")
        self.assertEqual(PollResponse.objects.get().answer, "Yes")
        self.assertIn("Do you want to tell us", out["reply_text"])
        self.assertFalse(Case.objects.exists())

    def test_no_is_counted_with_thanks(self):
        self.send("JOIN")
        send_poll(self.poll)
        self.assertIn("Thank you", self.send("2")["reply_text"])
        self.assertEqual(PollResponse.objects.get().answer, "No")

    def test_answering_twice_keeps_one_response(self):
        self.send("JOIN")
        send_poll(self.poll)
        self.send("1")
        send_poll(self.poll)
        self.send("2")
        self.assertEqual(PollResponse.objects.count(), 1)


@override_settings(HEATMAP_MIN=5)
class PollResultsTests(TestCase):
    def test_small_district_counts_are_hidden(self):
        poll = Poll.objects.create(question="Q?", options=["Yes", "No", "Skip"])
        for i in range(6):
            r = get_reporter("sms", f"+25670000{i:04d}", None)
            r.district = "Kampala"
            r.save()
            PollResponse.objects.create(poll=poll, reporter=r, answer="Yes", district="Kampala")
        for i in range(3):
            PollResponse.objects.create(poll=poll, answer="No", district="Gulu")
        rows = {row["district"]: row for row in results(poll)}
        self.assertEqual(rows["Kampala"]["total"], 6)
        self.assertIsNone(rows["Gulu"]["total"])
        self.assertTrue(rows["Gulu"]["hidden"])


class PollPageTests(TestCase):
    def setUp(self):
        seed()

    def test_staff_can_send_a_poll_and_see_results(self):
        self.client.login(username="sarah", password="habari-demo")
        poll = Poll.objects.first()
        self.assertIsNotNone(poll)  # seed_demo creates the default poll
        self.assertContains(self.client.get("/officer/polls"), poll.question)
        r = self.client.post(f"/officer/polls/{poll.id}/send")
        self.assertEqual(r.status_code, 302)

    def test_poll_page_needs_login(self):
        self.assertEqual(self.client.get("/officer/polls").status_code, 302)
