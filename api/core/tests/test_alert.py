from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from core import alert
from core.models import Case, Notification, Officer


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlertTests(TestCase):
    def setUp(self):
        call_command("seed_demo", verbosity=0)
        self.on_call = Officer.objects.filter(on_call=True)

    def case(self, severity, flags=None):
        return Case.objects.create(code=f"HB-ALRT{severity}{len(flags or [])}", channel="web", pick="2",
                                   severity=severity, category="sextortion", flags=flags or [])

    def test_serious_case_shows_on_the_on_call_officers_dashboard(self):
        case = self.case(4)
        alert.maybe_escalate(case)
        for officer in self.on_call:
            self.assertTrue(Notification.objects.filter(case=case, officer=officer).exists())

    def test_assigned_officer_is_told_too(self):
        case = self.case(3)
        case.assigned_officer = Officer.objects.filter(on_call=False).first()
        case.save()
        alert.maybe_escalate(case)
        self.assertTrue(Notification.objects.filter(case=case, officer=case.assigned_officer).exists())

    def test_running_twice_does_not_repeat_the_notice(self):
        case = self.case(4)
        alert.maybe_escalate(case)
        alert.maybe_escalate(case)
        self.assertEqual(Notification.objects.filter(case=case).count(), self.on_call.count())

    def test_low_severity_without_risk_flags_raises_no_alert(self):
        case = self.case(2)
        alert.maybe_escalate(case)
        self.assertFalse(Notification.objects.filter(case=case).exists())

    def test_officers_with_an_email_get_one(self):
        for officer in self.on_call:
            officer.user.email = f"{officer.user.username}@example.org"
            officer.user.save()
        alert.maybe_escalate(self.case(4))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("DANGER", mail.outbox[0].subject)

    def test_dashboard_shows_the_alert(self):
        case = self.case(4)
        alert.maybe_escalate(case)
        officer = self.on_call.first()
        self.client.force_login(officer.user)
        self.assertContains(self.client.get("/officer/", HTTP_HOST="localhost"), case.code)
