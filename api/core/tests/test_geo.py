import json

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.geo import nearest_district
from core.models import Case, Reporter
from core.tests.helpers import make_case, seed

KAMPALA = {"lat": 0.3476, "lon": 32.5825}


class NearestDistrictTests(TestCase):
    def test_known_points(self):
        self.assertEqual(nearest_district(0.35, 32.58), "Kampala")
        self.assertEqual(nearest_district(2.77, 32.30), "Gulu")
        self.assertEqual(nearest_district(-0.61, 30.65), "Mbarara")

    def test_outside_uganda_is_none(self):
        self.assertIsNone(nearest_district(51.5, -0.12))

    def test_bad_input_is_none(self):
        self.assertIsNone(nearest_district("x", None))


class LocationThroughGatewayTests(TestCase):
    def send(self, text, location=None, sender="web-geo"):
        body = {"sender_id": sender, "text": text, "location": location}
        return self.client.post("/api/channel/web", json.dumps(body), content_type="application/json").json()

    def test_t4_6_location_becomes_a_district_and_coordinates_are_not_kept(self):
        self.send("HELP")
        self.send("4")
        code = self.send("they call me names", location=KAMPALA)["case_code"]
        case = Case.objects.get(code=code)
        self.assertEqual(case.district, "Kampala")
        self.assertEqual(Reporter.objects.get().district, "Kampala")
        everything = json.dumps([{f.name: str(getattr(o, f.name)) for f in o._meta.fields}
                                 for o in [case, case.reporter]])
        self.assertNotIn("0.3476", everything)
        self.assertNotIn("32.58", everything)

    def test_location_alone_gets_a_short_thank_you(self):
        out = self.send("", location=KAMPALA)
        self.assertIn("Kampala", out["reply_text"])

    def test_later_cases_use_the_known_district(self):
        self.send("", location=KAMPALA)
        self.send("HELP")
        self.send("4")
        self.assertEqual(Case.objects.get(code=self.send("they call me names")["case_code"]).district, "Kampala")

    def test_district_command_for_basic_phones(self):
        body = {"sender_id": "+256700000001", "text": "DISTRICT gulu"}
        out = self.client.post("/api/channel/sms", json.dumps(body), content_type="application/json").json()
        self.assertIn("Gulu", out["reply_text"])
        self.assertEqual(Reporter.objects.get().district, "Gulu")

    def test_unknown_district_name_lists_examples(self):
        body = {"sender_id": "+256700000001", "text": "DISTRICT atlantis"}
        out = self.client.post("/api/channel/sms", json.dumps(body), content_type="application/json").json()
        self.assertIn("Kampala", out["reply_text"])
        self.assertEqual(Reporter.objects.get().district, "")


@override_settings(HEATMAP_MIN=5)
class HeatMapTests(TestCase):
    def setUp(self):
        seed()
        for i in range(6):
            make_case(district="Kampala", sender=f"+25670010{i:04d}")
        for i in range(3):
            make_case(district="Gulu", sender=f"+25670020{i:04d}")

    def test_t4_7_small_districts_show_no_number(self):
        self.client.login(username="sarah", password="habari-demo")
        rows = {r["district"]: r for r in self.client.get("/officer/map.json").json()["districts"]}
        self.assertEqual(rows["Kampala"]["count"], 6)
        self.assertIsNone(rows["Gulu"]["count"])
        self.assertNotIn("cases", json.dumps(rows))  # never individual points

    def test_map_needs_login(self):
        self.assertEqual(self.client.get("/officer/map.json").status_code, 302)

    def test_map_page_loads(self):
        self.client.login(username="sarah", password="habari-demo")
        self.assertContains(self.client.get("/officer/map"), "leaflet")

    def test_synthetic_demo_reports_are_labelled(self):
        call_command("seed_synthetic_reports", count=20, verbosity=0)
        demo = [c for c in Case.objects.all() if "synthetic_demo" in c.flags]
        self.assertEqual(len(demo), 20)


class LocationEntryPointTests(TestCase):
    def test_chat_page_asks_before_using_location(self):
        r = self.client.get("/chat")
        self.assertContains(r, 'id="share-location"')
        self.assertContains(r, "Share roughly where I am")

    def test_telegram_location_becomes_a_district(self):
        from channels.telegram import TelegramBot
        from channels.tests.test_telegram import FakeTelegram

        tg = FakeTelegram()
        TelegramBot("T", session=tg).handle_update(
            {"update_id": 1, "message": {"chat": {"id": 5}, "location": {"latitude": 2.77, "longitude": 32.30}}})
        self.assertIn("Gulu", tg.sent("sendMessage")[-1]["text"])
        self.assertEqual(Reporter.objects.get().district, "Gulu")
