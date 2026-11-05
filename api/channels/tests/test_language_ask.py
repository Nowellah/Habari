import json

from django.test import TestCase

from core.models import Case, Reporter

PHONE = "+256700000001"


class LanguageAskTests(TestCase):
    def send(self, text, **extra):
        body = {"sender_id": PHONE, "text": text, **extra}
        return self.client.post("/api/channel/sms", json.dumps(body), content_type="application/json").json()

    def report(self, pick, text, **extra):
        self.send("HELP")
        self.send(pick)
        return self.send(text, **extra)

    def test_t2_6_mixed_message_asks_language_after_creating_case(self):
        out = self.report("4", "help pliz mu school")
        self.assertIn("Which language is easiest", out["reply_text"])
        self.assertEqual(out["state"], "PICK_LANG")
        self.assertTrue(Case.objects.filter(code=out["case_code"]).exists())
        self.assertEqual([o["key"] for o in out["options"]], ["1", "2", "3", "4"])

    def test_answer_is_saved_on_case_and_reporter(self):
        code = self.report("4", "help pliz mu school")["case_code"]
        out = self.send("1")
        self.assertEqual(out["state"], "CASE_OPEN")
        self.assertEqual(Case.objects.get(code=code).language, "lg")
        self.assertEqual(Reporter.objects.get().language, "lg")

    def test_language_is_not_asked_twice(self):
        self.report("4", "help pliz mu school")
        self.send("1")
        out = self.report("4", "help pliz mu school")
        self.assertNotIn("Which language", out["reply_text"])

    def test_clear_english_is_not_asked(self):
        out = self.report("4", "they call me names at school every day")
        self.assertNotIn("Which language", out["reply_text"])
        self.assertEqual(out["state"], "CASE_OPEN")

    def test_language_given_by_channel_is_not_asked(self):
        out = self.report("4", "help pliz mu school", language="lg")
        self.assertNotIn("Which language", out["reply_text"])

    def test_danger_reply_never_asks_language(self):
        out = self.send("njagala okufa")
        self.assertTrue(out["reply_text"].startswith("Call 116"))
        self.assertNotIn("Which language", out["reply_text"])

    def test_free_text_instead_of_number_goes_to_case(self):
        code = self.report("4", "help pliz mu school")["case_code"]
        out = self.send("they also posted my photo")
        self.assertEqual(out["state"], "CASE_OPEN")
        self.assertEqual(Case.objects.get(code=code).messages.count(), 2)
