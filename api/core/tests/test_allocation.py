from django.test import TestCase, override_settings

from core import ai_triage, allocation
from core.models import Case, Officer
from core.tests.helpers import make_case, seed


class AllocationTests(TestCase):
    def setUp(self):
        seed()

    def test_t3_6_luganda_case_goes_to_a_luganda_speaker(self):
        c = make_case(category="self_harm", language="lg")
        officer = allocation.allocate(c)
        self.assertIn(officer.user.username, {"sarah", "moses"})
        self.assertIn("speaks Luganda", Case.objects.get(pk=c.pk).assignment_reason)

    def test_skill_and_district_decide_between_speakers(self):
        c = make_case(category="sextortion", language="en", district="Kampala")
        self.assertEqual(allocation.allocate(c).user.username, "joseph")  # cyber + Kampala

    def test_busy_officer_loses_to_a_free_one(self):
        joseph = Officer.objects.get(user__username="joseph")
        for _ in range(5):
            make_case(category="scam", assigned_officer=joseph)
        c = make_case(category="sextortion", language="en", district="Kampala")
        self.assertNotEqual(allocation.allocate(c).user.username, "joseph")

    def test_officer_with_conflict_is_never_chosen(self):
        Officer.objects.filter(user__username__in=["sarah", "moses"]).update(conflict_flag=True)
        c = make_case(category="self_harm", language="lg")
        self.assertNotIn(allocation.allocate(c).user.username, {"sarah", "moses"})

    def test_allocation_sets_status_and_reason(self):
        c = make_case(category="cyberbullying", language="en")
        allocation.allocate(c)
        c.refresh_from_db()
        self.assertEqual(c.status, Case.Status.ASSIGNED)
        self.assertTrue(c.assignment_reason.startswith("Assigned to "))

    def test_reassign_picks_a_different_officer(self):
        c = make_case(category="self_harm", language="lg")
        first = allocation.allocate(c)
        second = allocation.reassign_next(Case.objects.get(pk=c.pk), "no acknowledgement")
        self.assertNotEqual(first, second)
        self.assertIn("no acknowledgement", Case.objects.get(pk=c.pk).assignment_reason)

    @override_settings(AI_TRIAGE_INLINE=True)
    def test_cases_are_allocated_after_triage(self):
        c = make_case(severity=2, pick="4")
        ai_triage.apply(c.id, {"severity": 2, "category": "cyberbullying", "flags": [], "language": "en",
                               "language_confidence": 0.9, "role": ""})
        self.assertIsNotNone(Case.objects.get(pk=c.pk).assigned_officer)
