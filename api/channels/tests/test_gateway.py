import json

from django.test import TestCase

from core.models import Case, Conversation, Message, Reporter, ReporterVault

PHONE = "+256700000001"


class GatewayTestCase(TestCase):
    def send(self, text, channel="sms", sender=PHONE, **extra):
        body = {"channel": channel, "sender_id": sender, "text": text, **extra}
        r = self.client.post(f"/api/channel/{channel}", json.dumps(body), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def report(self, pick="2", text="a man keeps asking me for money"):
        self.send("HELP")
        self.send(pick)
        return self.send(text)


class MenuTests(GatewayTestCase):
    def test_help_shows_five_picks_and_calm_words(self):
        out = self.send("HELP")
        self.assertEqual(out["state"], "PICK_HARM")
        self.assertEqual([o["key"] for o in out["options"]], ["1", "2", "3", "4", "5"])
        self.assertTrue(out["reply_text"].startswith("Habari:"))
        self.assertIn("not in trouble", out["reply_text"])
        self.assertIsNone(out["case_code"])

    def test_response_has_contract_fields(self):
        out = self.send("HELP")
        self.assertEqual(set(out), {"reply_text", "options", "case_code", "state", "first_reply_ms"})

    def test_telegram_start_command_opens_menu(self):
        out = self.send("/start", channel="telegram", sender="tg:42")
        self.assertEqual(out["state"], "PICK_HARM")

    def test_invalid_pick_shows_menu_again(self):
        self.send("HELP")
        out = self.send("9")
        self.assertEqual(out["state"], "PICK_HARM")
        self.assertFalse(Case.objects.exists())

    def test_first_reply_is_fast(self):
        self.assertLess(self.send("HELP")["first_reply_ms"], 200)


class ReportTests(GatewayTestCase):
    def test_pick_1_creates_severity_4_case_with_helpline_first(self):
        self.send("HELP")
        out = self.send("1")
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(case.severity, 4)
        self.assertTrue(out["reply_text"].startswith("Call 116"))

    def test_pick_2_with_text_creates_severity_3_case_in_three_messages(self):
        out = self.report("2", "a man keeps asking me for money")
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(case.severity, 3)
        self.assertEqual(case.pick, "2")
        self.assertEqual(case.messages.get().text, "a man keeps asking me for money")
        self.assertIn(f"STATUS {case.code}", out["reply_text"])

    def test_description_starting_with_help_is_not_a_command(self):
        out = self.report("2", "help me please he wants my pictures")
        self.assertIsNotNone(out["case_code"])
        self.assertEqual(Case.objects.get(code=out["case_code"]).messages.get().text,
                         "help me please he wants my pictures")

    def test_zero_skips_the_description(self):
        out = self.report("4", "0")
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(case.severity, 2)
        self.assertFalse(case.messages.exists())

    def test_danger_phrase_in_first_message_skips_the_menu(self):
        out = self.send("I want to die")
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(case.severity, 4)
        self.assertIn("self_harm", case.flags)
        self.assertTrue(out["reply_text"].startswith("Call 116"))

    def test_keywords_raise_severity_above_the_pick(self):
        out = self.report("5", "he says he will leak my pictures")
        self.assertEqual(Case.objects.get(code=out["case_code"]).severity, 3)

    def test_follow_up_message_is_added_and_can_raise_severity(self):
        code = self.report("4", "they call me names")["case_code"]
        out = self.send("now i want to die")
        case = Case.objects.get(code=code)
        self.assertEqual(case.messages.count(), 2)
        self.assertEqual(case.severity, 4)
        self.assertTrue(out["reply_text"].startswith("Call 116"))

    def test_authority_words_set_alleged_role(self):
        code = self.report("4", "my teacher sends me messages at night")["case_code"]
        self.assertEqual(Case.objects.get(code=code).alleged_role, "authority")

    def test_pick_3_sets_alleged_role_authority(self):
        code = self.report("3", "0")["case_code"]
        self.assertEqual(Case.objects.get(code=code).alleged_role, "authority")

    def test_replies_never_repeat_case_details(self):
        out = self.report("2", "he wants my nude pictures")
        self.assertNotIn("nude", out["reply_text"].lower())
        self.assertNotIn("nude", self.send(f"STATUS {out['case_code']}")["reply_text"].lower())


class IdentityTests(GatewayTestCase):
    def test_same_number_is_one_reporter(self):
        self.send("HELP")
        self.send("HELP", sender="0700000001")
        self.assertEqual(Reporter.objects.count(), 1)

    def test_phone_number_lives_only_in_the_vault(self):
        code = self.report()["case_code"]
        self.assertEqual(ReporterVault.objects.get().raw_contact, PHONE)
        case = Case.objects.get(code=code)
        self.assertNotIn("700000001", json.dumps({f.name: str(getattr(case, f.name)) for f in case._meta.fields}))
        self.assertNotIn("700000001", case.reporter.pseudo_id)

    def test_web_channels_have_no_vault_entry(self):
        for channel, sender in (("web", "web-1"), ("extension", "ext-1"), ("siri", "siri-1")):
            self.send("HELP", channel=channel, sender=sender)
        self.assertFalse(ReporterVault.objects.exists())

    def test_sms_reporter_is_marked_basic_phone(self):
        self.send("HELP")
        self.assertTrue(Reporter.objects.get().basic_phone)


class CommandTests(GatewayTestCase):
    def test_status_returns_plain_words(self):
        code = self.report()["case_code"]
        out = self.send(f"status {code.lower()}")
        self.assertIn("We got your report", out["reply_text"])
        self.assertEqual(out["case_code"], code)

    def test_status_unknown_code(self):
        self.assertIn("could not find", self.send("STATUS HB-ZZZZZZ")["reply_text"])

    def test_stop_erases_thread_but_keeps_case(self):
        code = self.report()["case_code"]
        out = self.send("STOP")
        self.assertIn("will not message you again", out["reply_text"])
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(ReporterVault.objects.exists())
        self.assertTrue(Reporter.objects.get().opted_out)
        case = Case.objects.get(code=code)
        self.assertEqual(case.status, Case.Status.RECEIVED)
        self.assertIn("We got your report", self.send(f"STATUS {code}")["reply_text"])

    def test_messaging_again_after_stop_opts_back_in(self):
        self.send("HELP")
        self.send("STOP")
        self.send("HELP")
        self.assertFalse(Reporter.objects.get().opted_out)

    def test_pin_word_protects_status(self):
        code = self.report()["case_code"]
        self.assertIn("saved", self.send("PIN tiger")["reply_text"])
        self.assertIn("your word", self.send(f"STATUS {code}")["reply_text"])
        self.assertIn("your word", self.send(f"STATUS {code} lion")["reply_text"])
        self.assertIn("We got your report", self.send(f"STATUS {code} tiger")["reply_text"])

    def test_pin_word_is_not_stored_in_plain_text(self):
        self.send("PIN tiger")
        self.assertNotIn("tiger", Reporter.objects.get().pin_hash)


class RequestValidationTests(TestCase):
    def post(self, channel, body):
        return self.client.post(f"/api/channel/{channel}", json.dumps(body), content_type="application/json")

    def test_missing_sender_is_rejected(self):
        self.assertEqual(self.post("sms", {"text": "HELP"}).status_code, 400)

    def test_unknown_channel_is_rejected(self):
        self.assertEqual(self.post("pigeon", {"sender_id": "x", "text": "HELP"}).status_code, 404)

    def test_bad_json_is_rejected(self):
        r = self.client.post("/api/channel/sms", "{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get("/api/channel/sms").status_code, 405)

    def test_inbound_message_is_stored_on_case_only(self):
        self.post("sms", {"sender_id": PHONE, "text": "HELP"})
        self.assertFalse(Message.objects.exists())
