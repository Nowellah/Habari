import json

from channels.tests.test_gateway import GatewayTestCase
from core.models import Case


class AgeFlagTests(GatewayTestCase):
    def web(self, text, sender="web-a", **extra):
        body = {"channel": "web", "sender_id": sender, "text": text, **extra}
        r = self.client.post("/api/channel/web", json.dumps(body), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def report(self, meta):
        self.web("HELP", meta=meta)
        self.web("4", meta=meta)
        return self.web("someone keeps sending me rude messages", meta=meta, language="en")

    def test_the_chosen_age_group_is_kept_as_a_flag(self):
        self.report({"age_bracket": "10_12"})
        self.assertIn("age_10_12", Case.objects.get().flags)

    def test_skipping_or_nonsense_adds_no_flag(self):
        for i, value in enumerate(["none", "", "'; drop table", None]):
            self.report({"age_bracket": value} if value is not None else {"url": "https://x.test/a"})
        for case in Case.objects.all():
            self.assertFalse([f for f in case.flags if f.startswith("age_")])

    def test_a_chosen_language_skips_the_language_question(self):
        out = self.report({"age_bracket": "13_15"})
        self.assertNotIn("Which language", out["reply_text"])
