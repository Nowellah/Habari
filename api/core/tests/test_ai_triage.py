import json
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from core import ai_client
from core.models import Case

PHONE = "+256700000001"


def ai_result(**kw):
    base = {"pick_suggestion": "2", "category": "sextortion", "severity": 3, "role": "", "confidence": 0.85,
            "flags": ["sextortion"], "language": "en", "language_confidence": 0.9, "ask_language": False,
            "method": "rules"}
    base.update(kw)
    return base


@override_settings(AI_TRIAGE_INLINE=True)
class BackgroundTriageTests(TestCase):
    def setUp(self):
        stub = patch("core.ai_client.summarise", return_value=None)  # no real network in tests
        stub.start()
        self.addCleanup(stub.stop)

    def send(self, text):
        body = {"sender_id": PHONE, "text": text}
        return self.client.post("/api/channel/sms", json.dumps(body), content_type="application/json").json()

    def report(self, pick, text):
        self.send("HELP")
        self.send(pick)
        return self.send(text)["case_code"]

    def test_ai_runs_after_the_reply_not_before(self):
        with patch("core.ai_client.triage", return_value=ai_result()) as mock:
            with self.captureOnCommitCallbacks(execute=True):
                self.report("2", "he wants my pictures")
                self.assertFalse(mock.called)  # reply was built without waiting for AI
            self.assertTrue(mock.called)

    def test_ai_result_is_applied_to_the_case(self):
        with patch("core.ai_client.triage", return_value=ai_result(category="sextortion", language="en")):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report("2", "he wants my pictures")
        case = Case.objects.get(code=code)
        self.assertEqual(case.category, "sextortion")
        self.assertEqual(case.status, Case.Status.TRIAGED)
        self.assertEqual(case.triage_source, "ai")
        self.assertIsNotNone(case.triaged_at)

    def test_ai_can_raise_severity(self):
        with patch("core.ai_client.triage", return_value=ai_result(severity=4, flags=["self_harm"])):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report("4", "everyone is mean")
        case = Case.objects.get(code=code)
        self.assertEqual(case.severity, 4)
        self.assertIn("self_harm", case.flags)

    def test_ai_never_lowers_severity(self):
        with patch("core.ai_client.triage", return_value=ai_result(severity=1, category="inappropriate_content")):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report("2", "he wants my pictures")
        self.assertEqual(Case.objects.get(code=code).severity, 3)

    def test_ai_down_saves_case_as_high_for_human_review(self):
        with patch("core.ai_client.triage", return_value=None):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report("5", "something upsetting")
        case = Case.objects.get(code=code)
        self.assertGreaterEqual(case.severity, 3)
        self.assertIn("ai_unavailable", case.flags)
        self.assertEqual(case.triage_source, "rules_ai_down")

    def test_ai_role_sets_alleged_role(self):
        with patch("core.ai_client.triage", return_value=ai_result(role="authority")):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report("4", "he keeps messaging me")
        self.assertEqual(Case.objects.get(code=code).alleged_role, "authority")

    def test_follow_up_message_is_triaged_again(self):
        with patch("core.ai_client.triage", return_value=ai_result()) as mock:
            with self.captureOnCommitCallbacks(execute=True):
                self.report("2", "he wants my pictures")
            with self.captureOnCommitCallbacks(execute=True):
                self.send("now he wants money too")
        self.assertEqual(mock.call_count, 2)

    def test_officer_page_shows_how_the_case_was_triaged(self):
        with patch("core.ai_client.triage", return_value=None):
            with self.captureOnCommitCallbacks(execute=True):
                self.report("5", "something upsetting")
        user = User.objects.create_user("sarah", password="pw")
        user.groups.add(Group.objects.get_or_create(name="officer")[0])
        self.client.login(username="sarah", password="pw")
        self.assertContains(self.client.get("/officer/"), "Rules (AI down)")


class AiClientTests(TestCase):
    def test_a_real_danger_phrase_is_critical(self):
        with patch("ai_service.language.sunbird_client.language_id", return_value=None):
            self.assertEqual(ai_client.triage("I want to die", None, None)["severity"], 4)

    def test_a_crash_returns_none(self):
        with patch("core.ai_client.run_triage", side_effect=RuntimeError("boom")):
            self.assertIsNone(ai_client.triage("x", None, None))

    def test_an_odd_result_returns_none(self):
        with patch("core.ai_client.run_triage", return_value={}):
            self.assertIsNone(ai_client.triage("x", None, None))

    def test_a_good_result_is_returned(self):
        with patch("core.ai_client.run_triage", return_value=ai_result()):
            self.assertEqual(ai_client.triage("x", "2", None)["category"], "sextortion")

    def test_summary_failure_returns_none(self):
        with patch("core.ai_client.synthesis.summarise", side_effect=RuntimeError("boom")):
            self.assertIsNone(ai_client.summarise([{"text": "x"}]))


@override_settings(AI_TRIAGE_INLINE=True)
class SummaryOnCaseTests(TestCase):
    SUMMARY = {"summary": "- he wants my pictures", "timeline": [],
               "entities": {"handles": ["@x1"], "phones": [], "urls": [], "amounts_ugx": [50000],
                            "dates": [], "platforms": ["instagram"]}, "method": "extractive"}

    def report(self):
        body = lambda t: json.dumps({"sender_id": PHONE, "text": t})
        for t in ("HELP", "2"):
            self.client.post("/api/channel/sms", body(t), content_type="application/json")
        return self.client.post("/api/channel/sms", body("he wants my pictures"),
                                content_type="application/json").json()["case_code"]

    def test_summary_and_details_are_saved(self):
        with patch("core.ai_client.triage", return_value=ai_result()), \
             patch("core.ai_client.summarise", return_value=self.SUMMARY):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report()
        case = Case.objects.get(code=code)
        self.assertEqual(case.summary, "- he wants my pictures")
        self.assertEqual(case.entities["handles"], ["@x1"])

    def test_no_summary_when_ai_is_down(self):
        with patch("core.ai_client.triage", return_value=None), \
             patch("core.ai_client.summarise", return_value=None):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report()
        self.assertEqual(Case.objects.get(code=code).summary, "")

    def test_officer_sees_summary_and_details(self):
        with patch("core.ai_client.triage", return_value=ai_result()), \
             patch("core.ai_client.summarise", return_value=self.SUMMARY):
            with self.captureOnCommitCallbacks(execute=True):
                code = self.report()
        user = User.objects.create_user("sarah", password="pw")
        user.groups.add(Group.objects.get_or_create(name="officer")[0])
        self.client.login(username="sarah", password="pw")
        r = self.client.get(f"/officer/case/{code}/")
        self.assertContains(r, "he wants my pictures")
        self.assertContains(r, "@x1")
        self.assertContains(r, "50000")
