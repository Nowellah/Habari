from django.test import TestCase, override_settings
from django.utils import timezone

from core import router
from core.models import Case, Partner
from core.tests.helpers import after, make_case, seed
from partners_mock import mock

# Police CFPU acknowledges within 120 SLA minutes = 40 real seconds at scale 180.


@override_settings(SLA_TIME_SCALE=180, DEMO_SLOW_PARTNER="")
class MockPartnerTests(TestCase):
    def setUp(self):
        seed()
        self.t0 = timezone.now()

    def referral(self, slug="police_cfpu"):
        case = make_case(severity=3, pick="2", at=self.t0)
        partner = Partner.objects.get(slug=slug)
        return router.send_referrals(case, partners=[partner], now=self.t0)[0]

    def test_normal_partner_acknowledges_inside_its_window(self):
        ref = self.referral()
        mock.process_due(after(self.t0, 1))
        ref.refresh_from_db()
        self.assertIsNone(ref.ack_at)
        mock.process_due(after(self.t0, 10))
        ref.refresh_from_db()
        self.assertIsNotNone(ref.ack_at)
        self.assertIsNotNone(Case.objects.get(pk=ref.case_id).ack_at)

    @override_settings(DEMO_SLOW_PARTNER="police_cfpu")
    def test_slow_partner_misses_its_window(self):
        ref = self.referral()
        mock.process_due(after(self.t0, 45))
        ref.refresh_from_db()
        self.assertIsNone(ref.ack_at)

    def test_mock_inbox_keeps_the_payload(self):
        ref = self.referral()
        self.assertEqual(ref.mock_inbox.get().payload["case_code"], ref.case.code)


class AckEndpointTests(TestCase):
    def setUp(self):
        seed()
        case = make_case(severity=3, pick="2")
        self.ref = router.send_referrals(case, partners=[Partner.objects.get(slug="ucc")])[0]

    def post(self, key):
        return self.client.post(f"/api/referrals/{self.ref.id}/ack", HTTP_X_PARTNER_KEY=key)

    def test_wrong_key_is_refused(self):
        self.assertEqual(self.post("wrong").status_code, 403)
        self.ref.refresh_from_db()
        self.assertIsNone(self.ref.ack_at)

    def test_partner_key_acknowledges(self):
        self.assertEqual(self.post(self.ref.partner.api_key).status_code, 200)
        self.ref.refresh_from_db()
        self.assertIsNotNone(self.ref.ack_at)
