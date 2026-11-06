"""After the helpline, a danger report asks what the danger is, so the helper has more to go on."""
from channels.tests.test_gateway import GatewayTestCase
from core.models import Case


class DangerQuestionsTests(GatewayTestCase):
    def web(self, text, sender="web-d"):
        return self.send(text, sender=sender, channel="web")

    def start(self, sender="web-d"):
        self.web("HELP", sender)
        return self.web("1", sender)

    def test_the_helpline_comes_first_then_the_first_question(self):
        out = self.start()
        self.assertTrue(out["reply_text"].startswith("Call 116 now"))
        self.assertIn("Are you safe right now?", out["reply_text"])
        self.assertNotIn("1 Yes", out["reply_text"])
        self.assertEqual([o["key"] for o in out["options"]], ["1", "2", "3"])

    def test_not_safe_is_flagged_and_gets_a_reassuring_reply(self):
        self.start()
        out = self.web("2")
        self.assertIn("Call 116", out["reply_text"])
        self.assertIn("Who is the danger from?", out["reply_text"])
        self.assertEqual(len(out["options"]), 5)
        self.assertIn("child_not_safe", Case.objects.get().flags)

    def test_an_adult_in_charge_is_recorded_for_routing(self):
        self.start()
        self.web("1")
        out = self.web("3")
        case = Case.objects.get()
        self.assertEqual(case.alleged_role, "authority")
        self.assertIn("danger_from_authority", case.flags)
        self.assertEqual(out["options"], [{"key": "0", "label": "Skip"}])

    def test_skipping_the_last_question_finishes_and_severity_stays_critical(self):
        self.start()
        self.web("1")
        self.web("2")
        out = self.web("0")
        self.assertIn("A helper will read everything", out["reply_text"])
        self.assertEqual(Case.objects.get().severity, 4)
        self.assertEqual([o["key"] for o in out["options"]], ["PROOF_ADD", "PROOF_LATER"])

    def test_the_childs_own_words_at_the_last_question_are_kept(self):
        self.start()
        self.web("1")
        self.web("2")
        self.web("he is outside my door")
        self.assertTrue(Case.objects.get().messages.filter(text="he is outside my door").exists())

    def test_free_text_at_the_first_question_ends_the_questions_and_is_kept(self):
        self.start()
        self.web("he followed me home")
        self.assertTrue(Case.objects.get().messages.filter(text="he followed me home").exists())
        out = self.web("1")
        self.assertNotIn("Who is the danger from?", out["reply_text"])

    def test_a_danger_phrase_also_gets_the_questions(self):
        out = self.web("i will end it all tonight")
        self.assertIn("Call 116", out["reply_text"])
        self.assertIn("Are you safe right now?", out["reply_text"])

    def test_sms_is_not_asked_the_questions(self):
        self.send("HELP", sender="+256700000099", channel="sms")
        out = self.send("1", sender="+256700000099", channel="sms")
        self.assertNotIn("Are you safe", out["reply_text"])
        self.assertEqual(out["options"], [])
