from django.test import SimpleTestCase

from core.triage_rules import apply_rules, normalise_text


class NormaliseTests(SimpleTestCase):
    def test_lowercases_strips_punctuation_and_expands_shorthand(self):
        self.assertEqual(normalise_text("I WANNA die!!  pliz"), "i want to die please")


class FloorTests(SimpleTestCase):
    def test_self_harm_phrase_sets_severity_4_even_on_lowest_pick(self):
        r = apply_rules("I want to die", pick="5")
        self.assertEqual(r.severity, 4)
        self.assertIn("self_harm", r.flags)

    def test_sms_shorthand_self_harm_is_caught(self):
        self.assertEqual(apply_rules("i wanna die", pick="4").severity, 4)

    def test_luganda_draft_self_harm_term_is_caught(self):
        self.assertEqual(apply_rules("njagala okufa", pick=None).severity, 4)

    def test_pick_default_severity_applies_without_keywords(self):
        self.assertEqual(apply_rules("someone was rude", pick="4").severity, 2)
        self.assertEqual(apply_rules("", pick="1").severity, 4)

    def test_sextortion_terms_raise_to_3(self):
        r = apply_rules("he says he will leak my pictures", pick="5")
        self.assertEqual(r.severity, 3)

    def test_sextortion_with_money_and_threat_is_4(self):
        r = apply_rules("send money or else i will post my nude pictures", pick="2")
        self.assertEqual(r.severity, 4)

    def test_gambling_on_pick_5_raises_to_2(self):
        self.assertEqual(apply_rules("my friend made me try betting", pick="5").severity, 2)

    def test_short_term_matches_whole_words_only(self):
        # "bet" must not match inside "better" or "alphabet"
        self.assertEqual(apply_rules("I feel better about the alphabet test", pick="5").severity, 1)

    def test_keywords_never_lower_the_pick(self):
        self.assertEqual(apply_rules("it is fine now", pick="1").severity, 4)

    def test_authority_term_gives_role_hint(self):
        r = apply_rules("my teacher keeps messaging me", pick="4")
        self.assertEqual(r.role_hint, "authority")

    def test_no_pick_and_no_keywords_gives_severity_1(self):
        self.assertEqual(apply_rules("hello", pick=None).severity, 1)


class DangerFastPathTests(SimpleTestCase):
    PHRASES = [
        "i dont want to be alive anymore",
        "i will end it all tonight",
        "nobody would notice if i was gone",
        "no one would miss me",
    ]

    def test_indirect_danger_phrases_are_severity_4_even_on_the_lowest_pick(self):
        for phrase in self.PHRASES:
            with self.subTest(phrase):
                self.assertEqual(apply_rules(phrase, pick="5").severity, 4)

    def test_the_matching_rule_is_recorded_as_a_flag(self):
        self.assertIn("rule:danger_self_harm", apply_rules("i will end it all tonight").flags)

    def test_ordinary_text_is_not_raised(self):
        self.assertEqual(apply_rules("nobody would believe my story", pick="4").severity, 2)

    def test_empty_text_does_not_fail(self):
        self.assertEqual(apply_rules("", pick="5").severity, 1)
