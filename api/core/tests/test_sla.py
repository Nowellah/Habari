from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core import allocation, sla
from core.models import Case, Notification, Referral
from core.tests.helpers import after, make_case, seed


@override_settings(SLA_TIME_SCALE=180)  # 1 real minute = 3 SLA hours
class SlaClockTests(TestCase):
    def setUp(self):
        seed()
        self.t0 = timezone.now()

    def case(self, severity=3, **kw):
        c = make_case(severity=severity, at=self.t0, **kw)
        allocation.allocate(c)
        return Case.objects.get(pk=c.pk)

    def kinds(self, case):
        return list(case.sla_events.order_by("id").values_list("kind", flat=True))

    def test_t3_2_reminder_then_breach_then_escalation_in_order(self):
        c = self.case(3)
        sla.check(c, after(self.t0, 10))
        self.assertEqual(self.kinds(c), [])
        sla.check(Case.objects.get(pk=c.pk), after(self.t0, 21))   # 50% of 2 h ack
        sla.check(Case.objects.get(pk=c.pk), after(self.t0, 41))   # 100%
        sla.check(Case.objects.get(pk=c.pk), after(self.t0, 121))  # 150% of 4 h response
        self.assertEqual(self.kinds(c), ["ack_reminder", "ack_breach", "escalate_head"])

    def test_each_event_fires_once(self):
        c = self.case(3)
        for s in (41, 45, 50):
            sla.check(Case.objects.get(pk=c.pk), after(self.t0, s))
        self.assertEqual(self.kinds(c), ["ack_reminder", "ack_breach"])

    def test_breach_reassigns_and_tells_the_supervisor(self):
        c = self.case(3)
        first = c.assigned_officer
        sla.check(c, after(self.t0, 41))
        c.refresh_from_db()
        self.assertNotEqual(c.assigned_officer, first)
        self.assertTrue(Notification.objects.filter(case=c, audience="supervisor").exists())

    def test_escalation_refers_to_a_second_partner(self):
        c = self.case(3)
        sla.check(c, after(self.t0, 121))
        self.assertTrue(Referral.objects.filter(case=c).exists())

    def test_acknowledged_case_gets_no_ack_events(self):
        c = self.case(3, ack_at=self.t0)
        sla.check(c, after(self.t0, 50))
        self.assertEqual(self.kinds(c), [])

    def test_first_response_stops_escalation(self):
        c = self.case(3, ack_at=self.t0, first_response_at=self.t0)
        sla.check(c, after(self.t0, 200))
        self.assertEqual(self.kinds(c), [])

    def test_t3_3_severity_4_pages_on_call_and_reshows_helpline(self):
        c = self.case(4, pick="1")
        sla.check(c, after(self.t0, 6))  # 15 SLA minutes = 5 real seconds
        c.refresh_from_db()
        self.assertIn("page_on_call", self.kinds(c))
        self.assertIn("critical", c.flags)
        self.assertTrue(c.messages.filter(direction="out", text__contains="Call 116").exists())
        self.assertTrue(Notification.objects.filter(case=c, audience="on_call").exists())

    def test_closed_cases_are_ignored(self):
        c = self.case(3, status=Case.Status.CLOSED)
        sla.check(c, after(self.t0, 200))
        self.assertEqual(self.kinds(c), [])

    def test_reset_clock_lets_events_fire_again(self):
        c = self.case(3)
        sla.check(c, after(self.t0, 21))
        sla.reset_clock(c, "severity raised", now=after(self.t0, 30))
        c.refresh_from_db()
        self.assertEqual(c.clock_cycle, 1)
        sla.check(c, after(self.t0, 30 + 21))
        self.assertEqual(self.kinds(c).count("ack_reminder"), 2)

    def test_clock_colours(self):
        c = self.case(3)
        self.assertEqual(sla.clock_state(c, after(self.t0, 5))["colour"], "green")
        self.assertEqual(sla.clock_state(c, after(self.t0, 25))["colour"], "amber")
        self.assertEqual(sla.clock_state(c, after(self.t0, 45))["colour"], "red")

    def test_tick_checks_every_open_case(self):
        a, b = self.case(3), self.case(3)
        sla.tick(after(self.t0, 21))
        self.assertEqual(self.kinds(a), ["ack_reminder"])
        self.assertEqual(self.kinds(b), ["ack_reminder"])

    def test_watcher_command_runs_one_tick(self):
        call_command("run_sla_watcher", once=True, verbosity=0)
