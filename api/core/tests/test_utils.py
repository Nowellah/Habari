import re

from django.test import SimpleTestCase

from core.utils import new_case_code, normalise_msisdn, pseudo_id

SECRET = "test-secret"


class CaseCodeTests(SimpleTestCase):
    def test_case_code_has_prefix_and_six_unambiguous_characters(self):
        for _ in range(200):
            code = new_case_code()
            self.assertRegex(code, r"^HB-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$")

    def test_case_code_never_uses_confusable_characters(self):
        codes = "".join(new_case_code()[3:] for _ in range(500))
        self.assertIsNone(re.search(r"[01OIL]", codes))


class MsisdnTests(SimpleTestCase):
    def test_local_number_becomes_uganda_international(self):
        self.assertEqual(normalise_msisdn("0700 000 001"), "+256700000001")

    def test_international_without_plus_gets_plus(self):
        self.assertEqual(normalise_msisdn("256700000001"), "+256700000001")

    def test_already_normalised_is_unchanged(self):
        self.assertEqual(normalise_msisdn("+256700000001"), "+256700000001")


class PseudoIdTests(SimpleTestCase):
    def test_same_number_gets_same_id_across_phone_channels(self):
        a = pseudo_id("sms", "0700000001", SECRET)
        b = pseudo_id("ussd", "+256700000001", SECRET)
        self.assertEqual(a, b)

    def test_chat_id_never_collides_with_phone_number(self):
        phone = pseudo_id("sms", "+256700000001", SECRET)
        chat = pseudo_id("telegram", "tg:256700000001", SECRET)
        self.assertNotEqual(phone, chat)

    def test_id_depends_on_secret(self):
        self.assertNotEqual(pseudo_id("sms", "0700000001", "a"), pseudo_id("sms", "0700000001", "b"))

    def test_id_does_not_contain_the_number(self):
        pid = pseudo_id("sms", "0700000001", SECRET)
        self.assertNotIn("700000001", pid)
        self.assertEqual(len(pid), 20)
