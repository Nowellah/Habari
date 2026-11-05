import hashlib

from django.test import TestCase

from core.evidence import add_evidence, verify_chain
from core.models import Case, Evidence


class EvidenceChainTests(TestCase):
    def setUp(self):
        self.case = Case.objects.create(code="HB-AAAAAA", channel="sms", pick="2", severity=3)

    def test_first_entry_chains_from_zero_hash(self):
        e = add_evidence(self.case, "handle", "@stranger")
        self.assertEqual(e.prev_hash, "0" * 64)
        self.assertEqual(e.value_sha256, hashlib.sha256(b"@stranger").hexdigest())

    def test_second_entry_chains_from_first(self):
        first = add_evidence(self.case, "handle", "@stranger")
        second = add_evidence(self.case, "url", "https://example.org/p/1")
        self.assertEqual(second.prev_hash, first.chain_hash)

    def test_untouched_chain_verifies(self):
        add_evidence(self.case, "handle", "@stranger")
        add_evidence(self.case, "url", "https://example.org/p/1")
        self.assertTrue(verify_chain(self.case))

    def test_editing_an_old_entry_breaks_the_chain(self):
        first = add_evidence(self.case, "handle", "@stranger")
        add_evidence(self.case, "url", "https://example.org/p/1")
        Evidence.objects.filter(pk=first.pk).update(value="@someone_else")
        self.assertFalse(verify_chain(self.case))

    def test_chains_are_separate_per_case(self):
        other = Case.objects.create(code="HB-BBBBBB", channel="sms", pick="4", severity=2)
        add_evidence(self.case, "handle", "@a")
        e = add_evidence(other, "handle", "@b")
        self.assertEqual(e.prev_hash, "0" * 64)
