import json

from django.conf import settings
from django.test import TestCase

ALLOWED = {"Built", "Simulated", "Planned"}


class FeatureStatusTests(TestCase):
    def setUp(self):
        self.items = json.loads((settings.SHARED_DIR / "feature_status.json").read_text(encoding="utf8"))["features"]

    def test_every_feature_has_an_honest_label(self):
        self.assertGreaterEqual(len(self.items), 20)
        for f in self.items:
            self.assertIn(f["status"], ALLOWED, f["name"])
            self.assertTrue(f["note"], f["name"])

    def test_known_limits_are_not_called_built(self):
        by_name = {f["name"]: f["status"] for f in self.items}
        self.assertEqual(by_name["WhatsApp bot"], "Simulated")
        self.assertEqual(by_name["Partner services (Sauti 116, Police CFPU, UCC)"], "Simulated")
        self.assertEqual(by_name["Call with live transcript"], "Simulated")
        self.assertEqual(by_name["Hey Siri, Habari"], "Planned")

    def test_page_shows_the_labels(self):
        r = self.client.get("/about/status")
        self.assertContains(r, "WhatsApp bot")
        self.assertContains(r, "Simulated")
        self.assertContains(r, "Planned")
