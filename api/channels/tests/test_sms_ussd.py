from unittest.mock import patch

from django.test import TestCase, override_settings

from channels.sms import send_sms
from core.models import Case, OutboundSMS, Reporter

PHONE = "+256700000001"


class SmsHookTests(TestCase):
    def sms(self, text, frm=PHONE):
        r = self.client.post("/hooks/sms", {"from": frm, "to": "12345", "text": text})
        self.assertEqual(r.status_code, 200)
        return OutboundSMS.objects.order_by("-id").first().text

    def test_incoming_sms_gets_a_reply_in_outbox(self):
        # First message triggers language selection
        self.assertIn("language", self.sms("HELP").lower())

    def test_full_sms_report_in_three_messages(self):
        self.sms("HELP")     # → language question
        self.sms("4")        # → chose English → harm menu
        self.sms("2")        # → describe
        reply = self.sms("a man wants money for my pictures")
        case = Case.objects.get()
        self.assertIn(case.code, reply)
        self.assertEqual(case.channel, "sms")

    def test_outbox_stores_no_phone_number(self):
        self.sms("HELP")
        row = OutboundSMS.objects.get()
        self.assertNotIn("700000001", row.text + row.provider_status)

    def test_stop_confirmation_is_still_sent(self):
        self.sms("HELP")
        self.assertIn("will not message you again", self.sms("STOP"))

    def test_proactive_sms_is_not_sent_after_stop(self):
        self.sms("HELP")
        self.sms("STOP")
        before = OutboundSMS.objects.count()
        send_sms(Reporter.objects.get(), "Your case was updated")
        self.assertEqual(OutboundSMS.objects.count(), before)

    def test_missing_fields_rejected(self):
        self.assertEqual(self.client.post("/hooks/sms", {"text": "HELP"}).status_code, 400)

    @override_settings(AT_API_KEY="k", AT_USERNAME="sandbox")
    def test_provider_is_called_when_key_is_set(self):
        with patch("channels.sms.requests.post") as post:
            post.return_value.status_code = 201
            post.return_value.text = "ok"
            self.sms("HELP")
        url = post.call_args.args[0]
        self.assertIn("sandbox.africastalking.com", url)
        self.assertEqual(post.call_args.kwargs["data"]["to"], PHONE)
        self.assertEqual(post.call_args.kwargs["headers"]["apiKey"], "k")
        self.assertEqual(OutboundSMS.objects.get().provider, "africastalking")


class UssdTests(TestCase):
    def ussd(self, text, phone=PHONE):
        r = self.client.post("/hooks/ussd", {"sessionId": "s1", "phoneNumber": phone,
                                             "serviceCode": "*384*1#", "text": text})
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertTrue(body.startswith(("CON ", "END ")), body)
        self.assertLessEqual(len(body), 200, body)  # screens stay short (increased for new steps)
        return body

    def test_first_screen_is_main_menu(self):
        body = self.ussd("")
        self.assertTrue(body.startswith("CON "))
        self.assertIn("1 Report", body)

    def test_step2_shows_language_menu(self):
        body = self.ussd("1")
        self.assertTrue(body.startswith("CON "))
        self.assertIn("Luganda", body)

    def test_step3_shows_age_menu(self):
        body = self.ussd("1*4")  # main=1 (report), lang=4 (English)
        self.assertTrue(body.startswith("CON "))
        self.assertIn("old are you", body)

    def test_report_asks_what_happened(self):
        # main=1 (report), lang=4 (English), age=3 (13-15)
        self.assertIn("1 Danger", self.ussd("1*4*3"))

    def test_t2_5b_danger_ends_at_once_with_helpline(self):
        # main=1, lang=4, age=3, harm=1 (Danger)
        body = self.ussd("1*4*3*1")
        self.assertTrue(body.startswith("END Call 116"))
        case = Case.objects.get()
        self.assertEqual(case.severity, 4)
        self.assertIn(case.code, body)

    def test_t2_5_full_report_and_confirmation_sms(self):
        # main=1, lang=1 (Luganda), age=2, harm=2, feel=1, confirm=1
        self.assertIn("Luganda", self.ussd("1"))
        self.assertIn("emyaka", self.ussd("1*1"))            # chose Luganda → age menu in Luganda
        self.assertIn("Akabi", self.ussd("1*1*2"))          # chose age 10-12 → harm menu in Luganda
        self.assertIn("okiwulira", self.ussd("1*1*2*2").lower())  # harm 2 → feeling menu in Luganda
        self.assertIn("Weereza", self.ussd("1*1*2*2*1"))       # feeling 1 → confirm in Luganda
        body = self.ussd("1*1*2*2*1*1")                      # confirmed
        case = Case.objects.get()
        self.assertTrue(body.startswith("END "))
        self.assertIn(case.code, body)
        self.assertEqual(case.language, "lg")
        self.assertEqual(case.channel, "ussd")
        self.assertIn(case.code, OutboundSMS.objects.get().text)

    def test_ussd_feeling_scared_raises_the_case_to_severity_three(self):
        # main=1, lang=4, age=3, harm=5, feel=3, confirm=1
        self.ussd("1*4*3*5*3*1")
        case = Case.objects.get()
        self.assertGreaterEqual(case.severity, 3)
        self.assertIn("child_feels_scared", case.flags)

    def test_ussd_feeling_a_little_never_lowers_severity(self):
        # main=1, lang=4, age=3, harm=2, feel=1, confirm=1
        self.ussd("1*4*3*2*1*1")
        case = Case.objects.get()
        self.assertGreaterEqual(case.severity, 3)  # pick 2 starts at 3
        self.assertIn("child_feels_little", case.flags)

    def test_ussd_feeling_danger_ends_with_the_helpline(self):
        # main=1, lang=4, age=3, harm=5, feel=4, confirm=1
        body = self.ussd("1*4*3*5*4*1")
        self.assertTrue(body.startswith("END Call 116"))
        self.assertEqual(Case.objects.get().severity, 4)

    def test_ussd_feeling_can_be_skipped(self):
        # main=1, lang=4, age=3, harm=5, feel=0 (skip), confirm=1
        self.ussd("1*4*3*5*0*1")
        case = Case.objects.get()
        self.assertFalse(any(f.startswith("child_feels_") for f in case.flags))

    def test_ussd_invalid_feeling_ends_politely(self):
        # main=1, lang=4, age=3, harm=5, feel=9 (invalid)
        self.assertTrue(self.ussd("1*4*3*5*9").startswith("END "))

    def test_invalid_pick_ends_politely(self):
        # main=1, lang=4, age=3, harm=9 (invalid)
        self.assertTrue(self.ussd("1*4*3*9").startswith("END "))
        self.assertFalse(Case.objects.exists())

    def test_check_my_case(self):
        self.ussd("1*4*3*1")  # create a danger case (lang=English, age=13-15, harm=Danger)
        code = Case.objects.get().code
        self.assertIn("case code", self.ussd("3"))
        self.assertIn("We got your report", self.ussd(f"3*{code}"))

    def test_safety_tips(self):
        body = self.ussd("4")
        self.assertTrue(body.startswith("END "))
        self.assertIn("Do not pay", body)

    def test_talk_to_someone_creates_a_contact_request(self):
        body = self.ussd("2")
        case = Case.objects.get()
        self.assertIn("talk_request", case.flags)
        self.assertIn(case.code, body)

    def test_check_unknown_case(self):
        self.assertIn("could not find", self.ussd("3*HB-ZZZZZZ"))


class SimulatorPageTests(TestCase):
    def test_simulator_pages_load(self):
        for url in ("/sim/sms", "/sim/ussd"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_sms_outbox_feed(self):
        self.client.post("/hooks/sms", {"from": PHONE, "to": "12345", "text": "HELP"})
        data = self.client.get("/sim/sms/outbox", {"number": PHONE}).json()
        self.assertIn("language", data["messages"][-1]["text"].lower())

    @override_settings(SIMULATORS_ENABLED=False)
    def test_simulators_can_be_switched_off(self):
        self.assertEqual(self.client.get("/sim/sms").status_code, 404)
        self.assertEqual(self.client.get("/sim/sms/outbox", {"number": PHONE}).status_code, 404)
