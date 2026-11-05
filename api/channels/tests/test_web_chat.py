"""The web chat shows buttons, so replies carry no typed number lists, and free text is not ignored."""
from channels.tests.test_gateway import GatewayTestCase
from core.models import Case


class WebWordingTests(GatewayTestCase):
    def web(self, text, sender="web-1"):
        return self.send(text, sender=sender, channel="web")

    def test_menu_is_friendly_and_has_no_number_list(self):
        out = self.web("HELP")
        self.assertEqual(out["reply_text"], "Hi, I am Habari. You are not in trouble. What is happening?")
        self.assertEqual(len(out["options"]), 5)

    def test_describe_step_has_a_skip_button_and_no_reply_instruction(self):
        self.web("HELP")
        out = self.web("4")
        self.assertNotIn("Reply", out["reply_text"])
        self.assertEqual(out["options"], [{"key": "0", "label": "Skip"}])

    def test_feeling_question_has_no_number_list(self):
        self.web("HELP")
        self.web("5")
        out = self.web("someone keeps sending me rude messages")
        self.assertIn("How big does this feel?", out["reply_text"])
        self.assertNotIn("1 A little", out["reply_text"])
        self.assertEqual(out["options"][0], {"key": "1", "label": "A little"})

    def test_first_reply_is_short_parts_and_shows_the_code_once(self):
        self.web("HELP")
        self.web("5")
        first = self.web("someone keeps sending me rude messages")
        parts = first["reply_text"].split("\n\n")
        self.assertGreaterEqual(len(parts), 3)
        self.assertTrue(all(len(p) < 110 for p in parts))
        self.assertEqual(first["reply_text"].count(first["case_code"]), 1)
        self.assertNotIn("STATUS", first["reply_text"])
        self.assertNotIn("STOP", first["reply_text"])
        later = self.web("he also sent a picture")
        self.assertNotIn(first["case_code"], later["reply_text"])

    def test_danger_reply_has_the_helpline_first_and_the_code_once(self):
        self.web("HELP")
        out = self.web("1")
        self.assertTrue(out["reply_text"].startswith("Call 116 now."))
        self.assertEqual(out["reply_text"].count(out["case_code"]), 1)

    def test_sms_keeps_its_typed_list(self):
        out = self.send("HELP", sender="+256700000001", channel="sms")
        self.assertIn("Reply 1 Danger", out["reply_text"])


class FreeTextTests(GatewayTestCase):
    def web(self, text, sender="web-2"):
        return self.send(text, sender=sender, channel="web")

    def test_a_harm_description_at_the_start_opens_a_case(self):
        out = self.web("a man online is asking me for nude pictures")
        self.assertIsNotNone(out["case_code"])
        self.assertTrue(Case.objects.filter(code=out["case_code"]).exists())

    def test_an_unclear_description_is_kept_and_completed_by_the_pick(self):
        out = self.web("something happened yesterday and i feel strange")
        self.assertIsNone(out["case_code"])
        self.assertEqual(out["state"], "PICK_HARM")
        self.assertNotIn("Reply", out["reply_text"])
        done = self.web("5")
        case = Case.objects.get(code=done["case_code"])
        self.assertEqual(case.messages.get().text, "something happened yesterday and i feel strange")

    def test_one_or_two_words_still_open_the_menu(self):
        out = self.web("hello there")
        self.assertEqual(out["state"], "PICK_HARM")
        self.assertIsNone(out["case_code"])
        self.assertFalse(Case.objects.exists())
