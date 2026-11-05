import json

from django.test import TestCase

from core.models import Case, ReporterVault

# Sender format each channel adapter will use.
SENDERS = {
    "sms": "+256700000101",
    "ussd": "+256700000102",
    "voice": "+256700000103",
    "whatsapp": "+256700000104",
    "telegram": "tg:5550001",
    "web": "web-3f9a2c",
    "extension": "ext-7b1d44",
    "siri": "siri-91ac0e",
}


class EveryChannelTests(TestCase):
    def send(self, channel, text):
        body = {"sender_id": SENDERS[channel], "text": text}
        r = self.client.post(f"/api/channel/{channel}", json.dumps(body), content_type="application/json")
        self.assertEqual(r.status_code, 200, channel)
        return r.json()

    def test_every_channel_completes_a_report(self):
        for channel in SENDERS:
            with self.subTest(channel=channel):
                self.assertEqual(self.send(channel, "HELP")["state"], "PICK_HARM")
                self.assertEqual(self.send(channel, "2")["state"], "DESCRIBE")
                code = self.send(channel, "someone wants my pictures")["case_code"]
                self.assertEqual(Case.objects.get(code=code).channel, channel)

    def test_only_reachable_channels_store_a_contact(self):
        # Phone channels keep the number; Telegram keeps the chat id for follow-ups.
        for channel in SENDERS:
            self.send(channel, "HELP")
        self.assertEqual(ReporterVault.objects.count(), 5)
