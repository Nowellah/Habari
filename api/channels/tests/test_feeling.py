"""Every report asks the child how it feels. The answer can raise severity, never lower it."""
from channels.tests.test_gateway import GatewayTestCase
from core.models import Case


class FeelingQuestion(GatewayTestCase):
    def test_new_case_asks_how_it_feels_with_four_choices(self):
        out = self.report(pick="4", text="someone is being mean to me online")
        self.assertIn("How does this feel", out["reply_text"])
        self.assertEqual([o["key"] for o in out["options"]], ["1", "2", "3", "4", "0"])
        self.assertEqual(out["state"], "CASE_OPEN")

    def test_a_child_already_in_danger_is_not_asked(self):
        out = self.send("HELP")
        out = self.send("1")
        self.assertNotIn("How does this feel", out["reply_text"])
        self.assertEqual(out["options"], [])

    def test_danger_phrase_in_a_description_is_not_asked(self):
        out = self.report(pick="5", text="i want to die")
        self.assertNotIn("How does this feel", out["reply_text"])

    def test_the_question_is_asked_only_once(self):
        self.report(pick="4", text="someone is being mean to me online")
        self.send("1")
        out = self.send("1")  # now an ordinary message
        self.assertIn("added", out["reply_text"])


class FeelingRaisesSeverity(GatewayTestCase):
    def case_after(self, answer, pick="5", text="i saw something upsetting online"):
        self.report(pick=pick, text=text)
        out = self.send(answer)
        return out, Case.objects.get()

    def test_scared_raises_to_severity_three(self):
        _, case = self.case_after("3")
        self.assertGreaterEqual(case.severity, 3)
        self.assertIn("child_feels_scared", case.flags)

    def test_a_lot_raises_to_at_least_two(self):
        _, case = self.case_after("2")
        self.assertGreaterEqual(case.severity, 2)
        self.assertIn("child_feels_lot", case.flags)

    def test_in_danger_makes_it_critical_and_shows_the_helpline(self):
        out, case = self.case_after("4")
        self.assertEqual(case.severity, 4)
        self.assertIn("Call 116", out["reply_text"])

    def test_a_little_never_lowers_a_serious_case(self):
        out, case = self.case_after("1", pick="2", text="a man keeps asking me for money")
        self.assertGreaterEqual(case.severity, 3)
        self.assertIn("trained person", out["reply_text"])
        self.assertIn("child_feels_little", case.flags)

    def test_a_little_on_a_minor_case_gets_a_plain_thanks(self):
        out, case = self.case_after("1", pick="5", text="i saw something upsetting online")
        self.assertLess(case.severity, 3)
        self.assertNotIn("trained person", out["reply_text"])

    def test_skip_records_nothing(self):
        _, case = self.case_after("0")
        self.assertFalse(any(f.startswith("child_feels_") for f in case.flags))

    def test_raise_is_recorded_for_the_sla_clock(self):
        _, case = self.case_after("3")
        self.assertTrue(case.sla_events.filter(kind="severity_raised").exists())


class FeelingAnswerThatIsNotANumber(GatewayTestCase):
    def test_words_are_treated_as_more_information(self):
        self.report(pick="4", text="someone is being mean to me online")
        out = self.send("it started last week")
        self.assertIn("added", out["reply_text"])
        self.assertEqual(Case.objects.get().messages.filter(direction="in").count(), 2)

    def test_a_danger_phrase_instead_of_a_number_still_raises_to_critical(self):
        self.report(pick="4", text="someone is being mean to me online")
        out = self.send("i want to die")
        self.assertEqual(Case.objects.get().severity, 4)
        self.assertIn("Call 116", out["reply_text"])

    def test_status_command_still_works_while_the_question_is_open(self):
        out = self.report(pick="4", text="someone is being mean to me online")
        reply = self.send(f"STATUS {out['case_code']}")
        self.assertIn(out["case_code"], reply["reply_text"])
