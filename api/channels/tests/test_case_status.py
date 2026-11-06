import json
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from channels.gateway import _pin_hash
from core import tracking
from core.models import Case, Message, Reporter


def make_case(**kw):
    reporter = Reporter.objects.create(pseudo_id="p-track", channel="web")
    defaults = dict(code="HB-TRK001", reporter=reporter, channel="web", severity=3, summary="private details")
    return Case.objects.create(**{**defaults, **kw})


class TrackingTests(TestCase):
    def post(self, code="HB-TRK001", word=""):
        return self.client.post("/api/case-status", json.dumps({"code": code, "word": word}), content_type="application/json")

    def setUp(self):
        cache.clear()

    def test_a_new_case_is_received_and_waiting(self):
        make_case()
        data = self.post().json()
        self.assertEqual([s["state"] for s in data["steps"]], ["done", "current", "todo", "todo", "todo", "todo"])
        self.assertFalse(data["closed"])
        self.assertIn("within 2 hours", data["goal"])

    def test_progress_marks_earlier_steps_done_and_the_current_one(self):
        case = make_case(status=Case.Status.IN_PROGRESS, ack_at=timezone.now())
        data = tracking.track(case)
        self.assertEqual([s["state"] for s in data["steps"]], ["done", "done", "done", "current", "todo", "todo"])
        self.assertEqual(data["goal"], "")

    def test_a_closed_case_shows_how_long_it_took_and_skips_what_it_did_not_need(self):
        opened = timezone.now() - timedelta(days=3, hours=4)
        case = make_case(created_at=opened, status=Case.Status.CLOSED, closed_at=opened + timedelta(hours=5))
        data = tracking.track(case)
        self.assertTrue(data["closed"])
        self.assertEqual(data["took"], "5 hours")
        self.assertEqual(data["steps"][3]["state"], "skipped")
        self.assertEqual(data["steps"][5]["state"], "done")
        self.assertEqual(data["steps"][-1]["title"], "Closed")

    def test_an_open_case_counts_up_from_when_it_was_made(self):
        make_case(created_at=timezone.now() - timedelta(hours=2, minutes=10))
        self.assertEqual(self.post().json()["took"], "2 hours 10 min")

    def test_nothing_private_is_returned(self):
        case = make_case(category="sextortion", alleged_role="family")
        body = json.dumps(tracking.track(case))
        for secret in ("private details", "sextortion", "family", "severity"):
            self.assertNotIn(secret, body)

    def test_messages_for_the_child_are_shown_but_not_what_the_child_wrote(self):
        case = make_case()
        Message.objects.create(case=case, direction="in", text="my secret words", channel="web")
        Message.objects.create(case=case, direction="out", text="A helper is looking at this.", channel="web")
        data = self.post().json()
        self.assertEqual([m["text"] for m in data["messages"]], ["A helper is looking at this."])

    def test_unknown_code_is_a_gentle_404(self):
        r = self.post("HB-NOPE99")
        self.assertEqual(r.status_code, 404)
        self.assertIn("could not find", r.json()["message"])

    def test_a_secret_word_is_needed_when_one_was_set_and_wrong_guesses_are_limited(self):
        case = make_case()
        case.reporter.pin_hash = _pin_hash(case.reporter, "mango")
        case.reporter.save()
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.post(word="wrong").status_code, 403)
        self.assertEqual(self.post(word="MANGO").status_code, 200)
        for _ in range(8):
            self.post(word="guess")
        self.assertEqual(self.post(word="mango").status_code, 429)

    def test_the_code_is_not_case_sensitive(self):
        make_case()
        self.assertEqual(self.post("hb-trk001").status_code, 200)

    def test_human_durations(self):
        self.assertEqual(tracking.human(20), "less than a minute")
        self.assertEqual(tracking.human(60), "1 minute")
        self.assertEqual(tracking.human(3 * 86400 + 100), "3 days")
