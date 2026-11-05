from django.contrib.auth.models import User
from django.test import TestCase

from core import linking
from core.evidence import add_evidence
from core.models import CaseIdentifier
from core.tests.helpers import make_case, seed


def case_with(text, entities=None, sender="+256700000001"):
    c = make_case(sender=sender)
    c.messages.create(direction="in", text=text, channel="sms")
    c.entities = entities or {}
    c.save()
    linking.index_case(c)
    return c


class StrongLinkTests(TestCase):
    def test_same_handle_links_two_cases(self):
        a = case_with("he wants my pictures", {"handles": ["@Big_Boss77"]}, "+256700000001")
        b = case_with("this man is asking for money", {"handles": ["@big_boss77"]}, "+256700000002")
        links = linking.linked_cases(b)
        self.assertEqual([l["case"].code for l in links], [a.code])
        self.assertIn("same handle", links[0]["reason"])
        self.assertEqual(links[0]["strength"], "strong")

    def test_same_phone_number_links(self):
        a = case_with("x", {"phones": ["+256772123456"]}, "+256700000001")
        b = case_with("y", {"phones": ["+256772123456"]}, "+256700000002")
        self.assertEqual(linking.linked_cases(a)[0]["case"], b)

    def test_handle_from_extension_evidence_counts(self):
        a = case_with("x", {}, "+256700000001")
        add_evidence(a, "handle", "@stranger_1")
        linking.index_case(a)
        b = case_with("y", {"handles": ["@stranger_1"]}, "+256700000002")
        self.assertEqual(linking.linked_cases(b)[0]["case"], a)

    def test_different_handles_do_not_link(self):
        case_with("hello there friend", {"handles": ["@one"]}, "+256700000001")
        b = case_with("completely different words", {"handles": ["@two"]}, "+256700000002")
        self.assertEqual(linking.linked_cases(b), [])

    def test_identifiers_are_stored_hashed(self):
        case_with("x", {"handles": ["@secret_handle"], "phones": ["+256772123456"]})
        stored = " ".join(CaseIdentifier.objects.values_list("hashed", flat=True))
        self.assertNotIn("secret_handle", stored)
        self.assertNotIn("772123456", stored)

    def test_a_case_never_links_to_itself(self):
        a = case_with("x", {"handles": ["@solo"]})
        self.assertEqual(linking.linked_cases(a), [])


class SimilarWordingTests(TestCase):
    def test_similar_wording_is_a_weak_link(self):
        a = case_with("a man on instagram says he will post my nude pictures unless I pay", sender="+256700000001")
        b = case_with("man on instagram said he will post my nude pictures if I do not pay", sender="+256700000002")
        links = linking.linked_cases(b)
        self.assertEqual(links[0]["case"], a)
        self.assertEqual(links[0]["strength"], "weak")
        self.assertIn("similar wording", links[0]["reason"])

    def test_unrelated_wording_is_not_linked(self):
        case_with("they call me names at school every day", sender="+256700000001")
        b = case_with("I lost my school fees on a betting app", sender="+256700000002")
        self.assertEqual(linking.linked_cases(b), [])


class OfficerSeesLinksTests(TestCase):
    def test_case_page_lists_linked_cases(self):
        seed()
        a = case_with("x", {"handles": ["@repeat"]}, "+256700000001")
        b = case_with("y", {"handles": ["@repeat"]}, "+256700000002")
        self.client.login(username="sarah", password="habari-demo")
        r = self.client.get(f"/officer/case/{b.code}/")
        self.assertContains(r, "Linked cases")
        self.assertContains(r, a.code)
