import json

from django.test import TestCase, override_settings

from core import ai_triage, router
from core.models import Referral
from core.tests.helpers import make_case, seed


class RoutePlanTests(TestCase):
    def setUp(self):
        seed()

    def slugs(self, case):
        partners, note = router.plan_routes(case)
        return {p.slug for p in partners}, note

    def test_t3_1_teacher_case_routes_external_only(self):
        case = make_case(severity=3, pick="3", alleged_role="authority")
        slugs, note = self.slugs(case)
        self.assertEqual(slugs, {"sauti_116", "ucc", "counsellor", "police_cfpu"})
        self.assertIn("school and home routes skipped", note)

    def test_authority_found_in_text_on_another_pick_still_skips_school(self):
        case = make_case(severity=2, pick="4", alleged_role="authority", flags=["child_chose_school"])
        slugs, _ = self.slugs(case)
        self.assertNotIn("school_focal", slugs)
        self.assertIn("sauti_116", slugs)

    def test_peer_bullying_does_not_go_to_school_without_child_choice(self):
        slugs, _ = self.slugs(make_case(severity=2, pick="4"))
        self.assertEqual(slugs, {"counsellor", "ucc"})

    def test_child_choice_adds_the_school(self):
        slugs, _ = self.slugs(make_case(severity=2, pick="4", flags=["child_chose_school"]))
        self.assertIn("school_focal", slugs)

    def test_severity_4_goes_to_helpline_and_police(self):
        slugs, _ = self.slugs(make_case(severity=4, pick="1"))
        self.assertTrue({"sauti_116", "police_cfpu"} <= slugs)


class SendReferralTests(TestCase):
    def setUp(self):
        seed()

    def test_one_referral_per_partner_and_no_duplicates(self):
        case = make_case(severity=3, pick="3", alleged_role="authority")
        first = router.send_referrals(case)
        again = router.send_referrals(case)
        self.assertEqual(len(first), 4)
        self.assertEqual(again, [])
        self.assertEqual(Referral.objects.filter(case=case).count(), 4)

    def test_payload_carries_no_identity(self):
        case = make_case(severity=3, pick="2", sender="+256700000777")
        ref = router.send_referrals(case)[0]
        blob = json.dumps(ref.payload)
        self.assertIn(case.code, blob)
        self.assertNotIn("700000777", blob)
        self.assertNotIn(case.reporter.pseudo_id, blob)

    def test_escalation_adds_a_partner_not_yet_used(self):
        case = make_case(severity=2, pick="4")
        router.send_referrals(case)
        before = set(Referral.objects.filter(case=case).values_list("partner__slug", flat=True))
        extra = router.escalate_second_partner(case)
        self.assertIsNotNone(extra)
        self.assertNotIn(extra.partner.slug, before)


@override_settings(AI_TRIAGE_INLINE=True)
class AutoReferralTests(TestCase):
    def setUp(self):
        seed()

    def test_severity_4_is_referred_automatically_after_triage(self):
        case = make_case(severity=4, pick="1")
        ai_triage.apply(case.id, None)
        self.assertTrue(Referral.objects.filter(case=case, partner__slug="sauti_116").exists())

    def test_severity_3_waits_for_a_person(self):
        case = make_case(severity=3, pick="2")
        ai_triage.apply(case.id, None)
        self.assertFalse(Referral.objects.filter(case=case).exists())


class ReferralStatusTests(TestCase):
    """The child's status words follow the referral: sent -> referred, partner ack -> acknowledged."""

    def setUp(self):
        from core.tests.helpers import seed
        seed()

    def test_sending_referrals_marks_the_case_referred(self):
        from core.models import Case
        from core.router import send_referrals
        from core.tests.helpers import make_case
        case = make_case(severity=4, status=Case.Status.ASSIGNED)
        send_referrals(case)
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.REFERRED)

    def test_partner_ack_marks_the_case_acknowledged(self):
        from core.models import Case
        from core.router import acknowledge_referral, send_referrals
        from core.tests.helpers import make_case
        case = make_case(severity=4)
        ref = send_referrals(case)[0]
        acknowledge_referral(ref)
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.ACKNOWLEDGED)

    def test_a_late_ack_never_moves_a_resolved_case_back(self):
        from core.models import Case
        from core.router import acknowledge_referral, send_referrals
        from core.tests.helpers import make_case
        case = make_case(severity=4)
        ref = send_referrals(case)[0]
        Case.objects.filter(pk=case.pk).update(status=Case.Status.RESOLVED)
        acknowledge_referral(ref)
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.RESOLVED)
