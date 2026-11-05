"""Tests for the AI service (FastAPI). Run with: python manage.py test ai_service"""
from unittest import TestCase

from fastapi.testclient import TestClient

from ai_service.app import app
from ai_service.language import detect_language
from ai_service.triage import triage

client = TestClient(app)


class LanguageTests(TestCase):
    def test_plain_english_is_confident(self):
        r = detect_language("a man keeps asking me for money and pictures")
        self.assertEqual(r["language"], "en")
        self.assertGreaterEqual(r["confidence"], 0.6)
        self.assertFalse(r["ask_language"])

    def test_luganda_sentence_is_luganda(self):
        r = detect_language("Omuntu ansaba ssente nga tasindika bifaananyi byange")
        self.assertEqual(r["language"], "lg")
        self.assertFalse(r["ask_language"])

    def test_swahili_sentence_is_swahili(self):
        self.assertEqual(detect_language("mtu ananiomba pesa na picha zangu")["language"], "sw")

    def test_mixed_short_message_asks_language(self):
        self.assertTrue(detect_language("help pliz mu school")["ask_language"])

    def test_no_known_words_asks_language(self):
        r = detect_language("xyzzy qwerty")
        self.assertEqual(r["language"], "unknown")
        self.assertTrue(r["ask_language"])


class TriageTests(TestCase):
    def test_t2_1_luganda_sextortion(self):
        r = triage("Omuntu ansaba ssente nga tasindika bifaananyi byange", pick="2")
        self.assertEqual(r["category"], "sextortion")
        self.assertGreaterEqual(r["severity"], 3)
        self.assertEqual(r["language"], "lg")

    def test_t2_2_self_harm_is_4(self):
        r = triage("I want to die")
        self.assertEqual(r["severity"], 4)
        self.assertIn("self_harm", r["flags"])
        self.assertEqual(r["category"], "self_harm")
        self.assertEqual(r["pick_suggestion"], "1")

    def test_teacher_sets_authority_role(self):
        r = triage("my teacher sends me messages at night", pick="4")
        self.assertEqual(r["role"], "authority")

    def test_pick_3_is_exposure_by_authority(self):
        self.assertEqual(triage("", pick="3")["category"], "exposure_by_authority")

    def test_gambling_category(self):
        r = triage("my friend made me try betting", pick="5")
        self.assertEqual(r["category"], "gambling_or_betting")
        self.assertEqual(r["severity"], 2)

    def test_no_signal_has_low_confidence(self):
        self.assertLess(triage("hello there", pick=None)["confidence"], 0.6)

    def test_keyword_match_has_higher_confidence_than_none(self):
        self.assertGreater(triage("I want to die")["confidence"], triage("hello there")["confidence"])

    def test_classifier_can_raise_severity(self):
        fake = lambda text, labels: {"self_harm": 0.93}
        r = triage("I feel like disappearing forever", pick="5", classifier=fake)
        self.assertEqual(r["severity"], 4)
        self.assertEqual(r["category"], "self_harm")

    def test_classifier_never_lowers_rules(self):
        fake = lambda text, labels: {"inappropriate_content": 0.99}
        self.assertEqual(triage("I want to die", classifier=fake)["severity"], 4)

    def test_weak_classifier_score_is_ignored(self):
        fake = lambda text, labels: {"self_harm": 0.30}
        self.assertEqual(triage("someone was rude", pick="4", classifier=fake)["severity"], 2)

    def test_broken_classifier_falls_back_to_rules(self):
        def broken(text, labels):
            raise RuntimeError("model crashed")
        self.assertEqual(triage("I want to die", classifier=broken)["severity"], 4)


class EndpointTests(TestCase):
    def test_health(self):
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_triage_endpoint_contract(self):
        r = client.post("/triage", json={"text": "I want to die"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            set(r.json()),
            {"pick_suggestion", "category", "severity", "role", "confidence", "flags", "language",
             "language_confidence", "ask_language", "method"},
        )

    def test_language_endpoint(self):
        self.assertEqual(client.post("/language", json={"text": "nataka kufa sana"}).json()["language"], "sw")

    def test_translate_without_token_says_not_translated(self):
        r = client.post("/translate", json={"text": "webale", "source": "lg", "target": "en"}).json()
        self.assertFalse(r["translated"])
        self.assertEqual(r["text"], "webale")

    def test_overlong_text_is_rejected(self):
        self.assertEqual(client.post("/triage", json={"text": "a" * 6000}).status_code, 422)
