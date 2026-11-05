import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from core import followup
from core.models import Case, OutboundSMS, Reporter

WA = "256700000777"


def payload(message=None, statuses=None):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "PID"},
             "contacts": [{"wa_id": WA}]}
    if message:
        value["messages"] = [{"from": WA, "id": "wamid.1", "timestamp": "1", **message}]
    if statuses:
        value["statuses"] = statuses
    return {"object": "whatsapp_business_account", "entry": [{"id": "x", "changes": [{"field": "messages", "value": value}]}]}


def text(body):
    return payload({"type": "text", "text": {"body": body}})


class VerifyTests(TestCase):
    @override_settings(WHATSAPP_VERIFY_TOKEN="vt")
    def test_meta_verification_handshake(self):
        r = self.client.get("/hooks/whatsapp", {"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"})
        self.assertEqual((r.status_code, r.content), (200, b"42"))

    @override_settings(WHATSAPP_VERIFY_TOKEN="vt")
    def test_wrong_verify_token_is_refused(self):
        r = self.client.get("/hooks/whatsapp", {"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"})
        self.assertEqual(r.status_code, 403)


@override_settings(WHATSAPP_APP_SECRET="", WHATSAPP_TOKEN="", WHATSAPP_PHONE_ID="")
class MessageTests(TestCase):
    def post(self, body, **headers):
        raw = json.dumps(body)
        return self.client.post("/hooks/whatsapp", raw, content_type="application/json", **headers)

    def last_reply(self):
        return OutboundSMS.objects.filter(provider="whatsapp-simulator").last().text

    def test_without_credentials_replies_go_to_the_simulator_outbox(self):
        self.assertEqual(self.post(text("HELP")).status_code, 200)
        self.assertIn("not in trouble", self.last_reply())

    def test_full_report_over_whatsapp(self):
        self.post(text("HELP"))
        self.post(payload({"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "2", "title": "x"}}}))
        self.post(text("someone wants my pictures"))
        case = Case.objects.get()
        self.assertEqual(case.channel, "whatsapp")
        self.assertIn(case.code, self.last_reply())

    def test_same_number_as_sms_is_the_same_child(self):
        self.client.post("/api/channel/sms", json.dumps({"sender_id": "+" + WA, "text": "HELP"}),
                         content_type="application/json")
        self.post(text("HELP"))
        self.assertEqual(Reporter.objects.count(), 1)

    def test_location_becomes_a_district(self):
        self.post(payload({"type": "location", "location": {"latitude": 2.77, "longitude": 32.30}}))
        self.assertEqual(Reporter.objects.get().district, "Gulu")

    def test_voice_note_asks_to_type(self):
        self.post(payload({"type": "audio", "audio": {"id": "m1"}}))
        self.assertIn("type", self.last_reply())

    def test_delivery_status_updates_are_ignored(self):
        self.assertEqual(self.post(payload(statuses=[{"status": "delivered"}])).status_code, 200)
        self.assertFalse(OutboundSMS.objects.exists())

    @override_settings(WHATSAPP_TOKEN="tok", WHATSAPP_PHONE_ID="PID")
    def test_reply_goes_through_the_graph_api(self):
        with patch("channels.whatsapp.requests.post") as post:
            post.return_value.status_code = 200
            self.post(text("HELP"))
        url = post.call_args.args[0]
        self.assertIn("graph.facebook.com", url)
        self.assertTrue(url.endswith("/PID/messages"))
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(post.call_args.kwargs["json"]["to"], WA)

    @override_settings(WHATSAPP_APP_SECRET="s3cret")
    def test_unsigned_requests_are_refused_when_a_secret_is_set(self):
        self.assertEqual(self.post(text("HELP")).status_code, 403)

    @override_settings(WHATSAPP_APP_SECRET="s3cret")
    def test_correctly_signed_requests_are_accepted(self):
        raw = json.dumps(text("HELP")).encode()
        sig = "sha256=" + hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()
        r = self.client.post("/hooks/whatsapp", raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=sig)
        self.assertEqual(r.status_code, 200)

    def test_status_updates_reach_whatsapp_children(self):
        self.post(text("HELP"))
        self.post(text("2"))
        self.post(text("someone wants my pictures"))
        followup.set_status(Case.objects.get(), Case.Status.REFERRED)
        self.assertIn("A helper is working on your report", self.last_reply())
