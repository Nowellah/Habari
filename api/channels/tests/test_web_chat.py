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

    def test_a_plain_question_gets_a_reviewed_answer_and_no_case(self):
        out = self.web("Is it my fault if someone shared my photo?")
        self.assertIsNone(out["case_code"])
        self.assertEqual(out["state"], "START")
        self.assertIn("If this is happening to you, I can help.", out["reply_text"])
        self.assertEqual([o["key"] for o in out["options"]], ["REPORT", "MENU"])
        self.assertFalse(Case.objects.exists())

    def test_the_answer_button_opens_the_menu(self):
        self.web("Is it my fault if someone shared my photo?")
        self.assertEqual(len(self.web("REPORT")["options"]), 5)

    def test_a_question_that_describes_harm_is_still_a_report(self):
        out = self.web("why does he keep asking me for nude pictures?")
        self.assertIsNotNone(out["case_code"])

    def test_a_question_with_no_matching_answer_goes_to_the_menu(self):
        out = self.web("what is the capital of france?")
        self.assertEqual(out["state"], "PICK_HARM")

    def test_sms_never_gets_knowledge_answers(self):
        out = self.send("Is it my fault if someone shared my photo?", sender="+256700000009", channel="sms")
        self.assertNotIn("If this is happening to you", out["reply_text"])

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


class FirstMenuTests(GatewayTestCase):
    def web(self, text, sender="web-3"):
        return self.send(text, sender=sender, channel="web")

    def test_the_chat_opens_with_four_choices_and_no_case(self):
        out = self.web("MENU")
        self.assertEqual(out["state"], "OFFER")
        self.assertEqual([o["key"] for o in out["options"]], ["TALK", "REPORT", "PROOF", "ASK"])
        self.assertIsNone(out["case_code"])
        self.assertFalse(Case.objects.exists())

    def test_make_a_report_shows_the_harm_choices(self):
        self.web("MENU")
        out = self.web("REPORT")
        self.assertEqual(out["state"], "PICK_HARM")
        self.assertEqual(len(out["options"]), 5)
        self.assertEqual(out["reply_text"], "You are not in trouble. What is happening?")

    def test_talk_to_someone_gives_the_helpline_and_a_way_to_write(self):
        self.web("MENU")
        out = self.web("TALK")
        self.assertTrue(out["reply_text"].startswith("Call 116 any time."))
        self.assertEqual([o["key"] for o in out["options"]], ["REPORT", "MENU"])
        self.assertFalse(Case.objects.exists())

    def test_keep_proof_gives_the_reviewed_answer(self):
        self.web("MENU")
        out = self.web("PROOF")
        self.assertIn("Don't delete the messages", out["reply_text"])
        self.assertEqual([o["key"] for o in out["options"]], ["REPORT", "MENU"])

    def test_ask_a_question_answers_without_the_question_word(self):
        self.web("MENU")
        self.assertEqual(self.web("ASK")["state"], "ASK")
        out = self.web("keeping proof of the messages")
        self.assertEqual(out["state"], "ASK")
        self.assertIn("Don't delete the messages", out["reply_text"])
        self.assertFalse(Case.objects.exists())

    def test_ask_with_no_answer_offers_the_helpline(self):
        self.web("MENU")
        self.web("ASK")
        out = self.web("capital of france")
        self.assertIn("I do not have an answer for that.", out["reply_text"])
        self.assertIn("116", out["reply_text"])

    def test_describing_harm_while_asking_becomes_a_report(self):
        self.web("MENU")
        self.web("ASK")
        out = self.web("a man online is asking me for nude pictures")
        self.assertIsNotNone(out["case_code"])

    def test_back_to_menu_returns_to_the_four_choices(self):
        self.web("MENU")
        self.web("ASK")
        self.assertEqual(self.web("MENU")["state"], "OFFER")

    def test_help_still_opens_the_harm_choices(self):
        self.assertEqual(self.web("HELP")["state"], "PICK_HARM")

    def test_sms_menu_is_unchanged(self):
        out = self.send("MENU", sender="+256700000002", channel="sms")
        self.assertIn("Reply 1 Danger", out["reply_text"])

    def test_free_text_at_the_first_menu_is_not_thrown_away(self):
        self.web("MENU")
        out = self.web("something happened yesterday and i feel strange")
        self.assertEqual(out["state"], "PICK_HARM")
        self.assertEqual(out["reply_text"], "Thank you for telling me. Which of these is closest?")
        done = self.web("5")
        self.assertEqual(Case.objects.get(code=done["case_code"]).messages.get().text,
                         "something happened yesterday and i feel strange")

    def test_a_hacked_phone_is_a_report_even_from_the_first_menu(self):
        self.web("MENU")
        out = self.web("I think someone hacked my phone")
        self.assertIsNotNone(out["case_code"])
        case = Case.objects.get(code=out["case_code"])
        self.assertIn("account_takeover", case.flags)
        self.assertGreaterEqual(case.severity, 2)
