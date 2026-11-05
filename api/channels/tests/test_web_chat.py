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
        self.assertIn("How does this feel for you?", out["reply_text"])
        self.assertNotIn("1 A little", out["reply_text"])
        self.assertEqual(out["options"][0], {"key": "1", "label": "A little"})

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
