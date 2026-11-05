from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from core import allocation, router
from core.models import Case, Notification, OutboundSMS, Partner, Referral
from core.tests.helpers import make_case, seed


@override_settings(SLA_TIME_SCALE=180)
class OfficerCaseTests(TestCase):
    def setUp(self):
        seed()
        self.case = make_case(severity=3, pick="3", alleged_role="authority", category="exposure_by_authority",
                              sender="+256700000888")
        self.case.messages.create(direction="in", text="my teacher touches me", channel="sms")
        self.client.login(username="sarah", password="habari-demo")

    def url(self, action=""):
        return f"/officer/case/{self.case.code}/{action}"

    def test_case_page_shows_details_but_no_identity(self):
        r = self.client.get(self.url())
        self.assertContains(r, self.case.code)
        self.assertContains(r, "exposure_by_authority")
        self.assertNotContains(r, "700000888")
        self.assertNotContains(r, self.case.reporter.pseudo_id)

    def test_t3_1_rule_is_visible_on_screen(self):
        self.assertContains(self.client.get(self.url()), "school and home routes skipped")

    def test_acknowledge(self):
        self.client.post(self.url("ack"))
        self.assertIsNotNone(Case.objects.get(pk=self.case.pk).ack_at)

    def test_reviewed_reply_reaches_child_and_counts_as_first_response(self):
        self.client.post(self.url("reply"), {"template": "read"})
        c = Case.objects.get(pk=self.case.pk)
        self.assertIsNotNone(c.first_response_at)
        self.assertTrue(c.messages.filter(direction="out").exists())
        self.assertTrue(OutboundSMS.objects.exists())

    def test_only_reviewed_replies_can_be_sent(self):
        self.assertEqual(self.client.post(self.url("reply"), {"template": "anything I like"}).status_code, 400)

    def test_send_referrals_button(self):
        self.client.post(self.url("refer"))
        self.assertEqual(Referral.objects.filter(case=self.case).count(), 4)
        self.assertEqual(Case.objects.get(pk=self.case.pk).status, Case.Status.REFERRED)

    def test_close_needs_a_reason(self):
        self.assertEqual(self.client.post(self.url("close"), {}).status_code, 400)
        self.client.post(self.url("close"), {"reason": "unfounded", "note": "checked twice"})
        c = Case.objects.get(pk=self.case.pk)
        self.assertEqual(c.status, Case.Status.CLOSED_UNFOUNDED)
        self.assertIsNotNone(c.closed_at)

    def test_resolve_schedules_safety_check_in(self):
        self.client.post(self.url("status"), {"status": "resolved"})
        c = Case.objects.get(pk=self.case.pk)
        self.assertEqual(c.status, Case.Status.RESOLVED)
        self.assertIsNotNone(c.checkin_due_at)

    def test_reassign_is_for_supervisors_only(self):
        peter = User.objects.get(username="peter").officer
        self.assertEqual(self.client.post(self.url("reassign"), {"officer": peter.id}).status_code, 403)
        self.client.login(username="esther", password="habari-demo")
        self.client.post(self.url("reassign"), {"officer": peter.id})
        c = Case.objects.get(pk=self.case.pk)
        self.assertEqual(c.assigned_officer, peter)
        self.assertIn("esther", c.assignment_reason)

    def test_unknown_case_is_404(self):
        self.assertEqual(self.client.get("/officer/case/HB-ZZZZZZ/").status_code, 404)

    def test_actions_need_login(self):
        self.client.logout()
        self.client.post(self.url("ack"))
        self.assertIsNone(Case.objects.get(pk=self.case.pk).ack_at)


@override_settings(SLA_TIME_SCALE=180)
class QueueAndBoardTests(TestCase):
    def setUp(self):
        seed()
        c = make_case(severity=3, category="sextortion", language="en", district="Kampala")
        allocation.allocate(c)

    def test_queue_shows_clock_and_assigned_officer(self):
        self.client.login(username="sarah", password="habari-demo")
        r = self.client.get("/officer/")
        self.assertContains(r, "clock-green")
        self.assertContains(r, "joseph")

    def test_supervisor_sees_notifications(self):
        Notification.objects.create(case=Case.objects.get(), audience="supervisor", text="Breach on case")
        self.client.login(username="esther", password="habari-demo")
        self.assertContains(self.client.get("/officer/"), "Breach on case")

    def test_partner_board_shows_median_and_breach_rate(self):
        case = Case.objects.get()
        t0 = timezone.now() - timedelta(hours=1)
        ucc = Partner.objects.get(slug="ucc")
        Referral.objects.create(case=case, partner=ucc, sent_at=t0, ack_at=t0 + timedelta(seconds=60))
        Referral.objects.create(case=case, partner=ucc, sent_at=t0, ack_at=t0 + timedelta(seconds=120))
        self.client.login(username="sarah", password="habari-demo")
        r = self.client.get("/officer/partners")
        self.assertContains(r, ucc.name)
        self.assertContains(r, "270")   # median 90 s real = 270 SLA minutes at scale 180
        self.assertContains(r, "0%")    # both inside UCC's 24 h window
