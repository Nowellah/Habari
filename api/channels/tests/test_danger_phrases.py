"""A danger phrase the keyword list does not know still gets the helpline in the first reply."""
from channels.tests.test_gateway import GatewayTestCase
from core.models import Case

PHRASES = [
    "i dont want to be alive anymore",
    "i will end it all tonight",
    "nobody would notice if i was gone",
]


class IndirectDangerPhrases(GatewayTestCase):
    def sender(self, index):
        return f"+25670000{index:04d}"

    def test_at_the_start_the_reply_is_the_helpline_not_the_menu(self):
        for i, phrase in enumerate(PHRASES):
            with self.subTest(phrase):
                out = self.send(phrase, sender=self.sender(i))
                self.assertIn("Call 116", out["reply_text"])
                self.assertEqual(out["state"], "CASE_OPEN")
                self.assertEqual(out["options"], [])

    def test_as_a_description_the_child_is_not_asked_how_it_feels(self):
        for i, phrase in enumerate(PHRASES):
            with self.subTest(phrase):
                sender = self.sender(10 + i)
                self.send("HELP", sender=sender)
                self.send("5", sender=sender)
                out = self.send(phrase, sender=sender)
                self.assertIn("Call 116", out["reply_text"])
                self.assertNotIn("How does this feel", out["reply_text"])

    def test_as_a_later_message_the_reply_is_the_helpline(self):
        for i, phrase in enumerate(PHRASES):
            with self.subTest(phrase):
                sender = self.sender(20 + i)
                self.send("HELP", sender=sender)
                self.send("4", sender=sender)
                self.send("someone is being mean to me", sender=sender)
                out = self.send(phrase, sender=sender)
                self.assertIn("Call 116", out["reply_text"])

    def test_every_such_case_is_critical(self):
        for i, phrase in enumerate(PHRASES):
            self.send(phrase, sender=self.sender(30 + i))
        self.assertEqual(Case.objects.filter(severity=4).count(), len(PHRASES))
