"""A child who writes in Luganda is answered in Luganda, on every channel and in every later message."""
import json
import re

from django.conf import settings
from django.test import SimpleTestCase

from channels.tests.test_gateway import GatewayTestCase
from core import followup
from core.messages import _messages, child_language, status_words
from core.models import Case

SEXTORTION_LG = "omusajja gwe nnasisinkana ku mutimbagano ansaba ssente oba ajja kusasaanya ebifaananyi byange"
BULLYING_LG = "abaana ku ssomero bampita amannya buli lunaku era bansekerera"


class LugandaWebTests(GatewayTestCase):
    def web(self, text, sender="web-lg"):
        return self.send(text, channel="web", sender=sender)

    def test_luganda_greeting_gets_the_luganda_menu(self):
        out = self.web("oli otya")
        self.assertIn("Toli mu buzibu", out["reply_text"])
        self.assertIn("Loopa ekizibu", [o["label"] for o in out["options"]])

    def test_luganda_report_gets_luganda_reply_and_buttons(self):
        self.web("oli otya")
        self.web("REPORT")
        self.web("4")
        out = self.web(BULLYING_LG)
        self.assertIn("Weebale okuntegeeza", out["reply_text"])
        self.assertIn(out["case_code"], out["reply_text"])
        self.assertEqual([o["label"] for o in out["options"]][:2], ["Katono", "Nnyo"])

    def test_luganda_sextortion_gets_helpline_first_and_luganda_advice(self):
        self.web("HELP")
        self.web("2")
        out = self.web(SEXTORTION_LG)
        self.assertTrue(out["reply_text"].startswith("Kuba ku 116"))
        self.assertIn("tosasula", out["reply_text"])
        self.assertEqual(Case.objects.get(code=out["case_code"]).severity, 4)

    def test_short_answers_keep_the_language(self):
        self.web("HELP")
        self.web("4")
        self.web(BULLYING_LG)
        out = self.web("2")  # "A lot", a bare number says nothing about language
        self.assertIn("Weebale", out["reply_text"])

    def test_status_check_is_in_luganda(self):
        self.web("HELP")
        self.web("4")
        code = self.web(BULLYING_LG)["case_code"]
        out = self.web(f"STATUS {code}")
        self.assertTrue(out["reply_text"].startswith(f"Ensonga {code}:"))

    def test_choosing_luganda_switches_the_next_reply(self):
        self.web("HELP")
        self.web("5")
        out = self.web("zzk qqv wwx")  # no language we can place, so Habari asks
        self.assertEqual(out["state"], "PICK_LANG")
        out = self.web("1")  # 1 = Luganda
        self.assertIn("Kino okiwulira", out["reply_text"])
        self.assertEqual(out["options"][0]["label"], "Katono")

    def test_english_stays_english(self):
        self.web("HELP", sender="web-en")
        self.web("4", sender="web-en")
        out = self.web("people in my class keep calling me names", sender="web-en")
        self.assertIn("Thank you for telling me", out["reply_text"])


class LugandaSmsTests(GatewayTestCase):
    def test_sms_report_in_luganda_is_answered_in_luganda(self):
        self.send("HELP")
        self.send("4")
        out = self.send(BULLYING_LG)
        self.assertIn("Weebale. Si nsobi yo.", out["reply_text"])
        self.assertIn("Ddamu 0", out["reply_text"])


class LugandaFollowUpTests(GatewayTestCase):
    def test_status_update_reaches_the_child_in_luganda(self):
        self.send("HELP")
        self.send("4")
        case = Case.objects.get(code=self.send(BULLYING_LG)["case_code"])
        self.assertEqual(child_language(case), "lg")
        sent = []
        original = followup.send_to_child
        followup.send_to_child = lambda c, text: sent.append(text)
        try:
            followup.set_status(case, Case.Status.REFERRED)
        finally:
            followup.send_to_child = original
        self.assertTrue(sent and "Omuyambi akola ku nsonga yo" in sent[0])
        self.assertTrue(status_words(case, "lg").startswith("Ensonga"))


class LugandaFileTests(SimpleTestCase):
    """The Luganda file must never break a reply: same placeholders, same labels."""

    def setUp(self):
        self.en, self.lg = _messages("en"), _messages("lg")

    def test_every_text_keeps_the_english_placeholders(self):
        for key, text in self.lg.items():
            if isinstance(text, str) and key in self.en and not key.startswith("_"):
                with self.subTest(key):
                    self.assertEqual(set(re.findall(r"{(\w+)}", text)), set(re.findall(r"{(\w+)}", self.en[key])))

    def test_every_label_and_status_is_translated(self):
        self.assertEqual(set(self.lg["labels"]), set(self.en["labels"]))
        self.assertEqual(set(self.lg["status"]), set(self.en["status"]))

    def test_harm_menu_has_luganda_short_labels(self):
        picks = json.loads((settings.SHARED_DIR / "harm_picker.json").read_text(encoding="utf8"))["picks"]
        self.assertTrue(all(p.get("short_lg") for p in picks))
