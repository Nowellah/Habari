"""The rule engine feeds the case engine's triage and can only raise severity."""
import unittest
from unittest import mock

from ai_service import triage as triage_module
from ai_service.engine import bridge
from ai_service.triage import triage


class EngineRaisesSeverity(unittest.TestCase):
    def test_indirect_self_harm_phrase_is_critical(self):
        r = triage("i dont want to be alive anymore")
        self.assertEqual(r["severity"], 4)
        self.assertEqual(r["category"], "self_harm")

    def test_payment_demand_with_threat_to_post_photos_is_sextortion(self):
        r = triage("he said send money or he will post my photos")
        self.assertGreaterEqual(r["severity"], 3)
        self.assertEqual(r["category"], "sextortion")

    def test_request_for_pictures_is_grooming(self):
        r = triage("he asked me to send him pics of me")
        self.assertGreaterEqual(r["severity"], 2)
        self.assertEqual(r["category"], "grooming")

    def test_account_scam_is_detected(self):
        r = triage("someone hacked my account and asks for money")
        self.assertGreaterEqual(r["severity"], 2)
        self.assertEqual(r["category"], "scam")

    def test_trusted_adult_harm_is_external_only_authority(self):
        r = triage("my teacher keeps touching me")
        self.assertEqual(r["role"], "authority")
        self.assertEqual(r["category"], "exposure_by_authority")
        self.assertGreaterEqual(r["severity"], 3)

    def test_rule_ids_are_reported_as_flags(self):
        r = triage("i dont want to be alive anymore")
        self.assertTrue(any(f.startswith(bridge.FLAG_PREFIX) for f in r["flags"]))

    def test_method_names_the_engine(self):
        self.assertEqual(triage("hello there")["method"], "rules+engine")


class EngineNeverLowers(unittest.TestCase):
    def test_danger_pick_stays_critical_on_harmless_text(self):
        self.assertEqual(triage("hello", pick="1")["severity"], 4)

    def test_existing_rule_severity_is_kept(self):
        self.assertEqual(triage("an older man wants to meet me alone")["severity"], 4)

    def test_empty_text_does_not_run_the_engine(self):
        with mock.patch.object(triage_module.bridge, "assess") as assess:
            triage("", pick="3")
        assess.assert_not_called()


class EngineFailure(unittest.TestCase):
    def test_unavailable_engine_leaves_the_rules_result(self):
        with mock.patch.object(triage_module.bridge, "assess", return_value=None):
            r = triage("i want to die")
        self.assertEqual(r["severity"], 4)
        self.assertEqual(r["method"], "rules")

    def test_assess_returns_none_when_the_engine_raises(self):
        with mock.patch.object(bridge, "safe_triage", side_effect=RuntimeError("boom")):
            self.assertIsNone(bridge.assess("anything"))


class CategoryMapping(unittest.TestCase):
    def test_other_category_leaves_the_case_engine_category_alone(self):
        self.assertIsNone(bridge.assess("hello there").category)

    def test_abuse_by_a_trusted_adult_maps_to_exposure_by_authority(self):
        self.assertEqual(bridge.assess("my uncle hits me at home").category, "exposure_by_authority")
