from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from core.models import Case, Officer, Partner, Reporter


class StatusPageTests(TestCase):
    def setUp(self):
        self.case = Case.objects.create(code="HB-ABCDEF", channel="sms", pick="2", severity=3)
        self.case.messages.create(direction="in", text="he wants my nude pictures", channel="sms")

    def test_status_page_shows_plain_words_and_helpline(self):
        r = self.client.get("/status/HB-ABCDEF")
        self.assertContains(r, "We got your report")
        self.assertContains(r, "116")

    def test_pages_use_the_habari_name(self):
        self.assertContains(self.client.get("/status/HB-ABCDEF"), "<title>Habari</title>")

    def test_status_page_never_shows_details(self):
        self.assertNotContains(self.client.get("/status/HB-ABCDEF"), "nude")

    def test_unknown_code_is_404(self):
        self.assertEqual(self.client.get("/status/HB-ZZZZZZ").status_code, 404)

    def test_code_lookup_ignores_case(self):
        self.assertEqual(self.client.get("/status/hb-abcdef").status_code, 200)


class OfficerListTests(TestCase):
    def setUp(self):
        reporter = Reporter.objects.create(pseudo_id="abc123secretpseudo0", channel="sms")
        Case.objects.create(code="HB-LOWLOW", channel="web", pick="5", severity=1)
        Case.objects.create(code="HB-HIGHHI", channel="sms", pick="1", severity=4, reporter=reporter)
        self.officer = User.objects.create_user("sarah", password="pw")
        self.officer.groups.add(Group.objects.get_or_create(name="officer")[0])

    def test_anonymous_user_is_sent_to_officer_login(self):
        r = self.client.get("/officer/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/login/"))

    def test_officer_without_admin_rights_can_log_in_on_login_page(self):
        r = self.client.post("/login/", {"username": "sarah", "password": "pw"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/officer/")
        self.assertContains(self.client.get("/officer/"), "HB-HIGHHI")

    def test_pages_do_not_use_no_referrer_policy(self):
        # With "no-referrer", browsers send "Origin: null" on form posts and
        # Django's CSRF check rejects the login with 403.
        self.assertNotContains(self.client.get("/login/"), 'content="no-referrer"')

    def test_browser_style_login_with_csrf_and_origin_succeeds(self):
        from django.test import Client
        browser = Client(enforce_csrf_checks=True)
        browser.get("/login/")
        token = browser.cookies["csrftoken"].value
        r = browser.post("/login/", {"username": "sarah", "password": "pw", "csrfmiddlewaretoken": token},
                         HTTP_ORIGIN="http://testserver")
        self.assertEqual(r.status_code, 302)

    def test_wrong_password_shows_an_error(self):
        r = self.client.post("/login/", {"username": "sarah", "password": "wrong"})
        self.assertContains(r, "did not match")

    def test_logout_ends_the_session(self):
        self.client.login(username="sarah", password="pw")
        self.client.post("/logout/")
        self.assertEqual(self.client.get("/officer/").status_code, 302)

    def test_user_without_role_is_refused(self):
        User.objects.create_user("visitor", password="pw")
        self.client.login(username="visitor", password="pw")
        self.assertEqual(self.client.get("/officer/").status_code, 403)

    def test_officer_sees_most_urgent_first(self):
        self.client.login(username="sarah", password="pw")
        html = self.client.get("/officer/").content.decode()
        self.assertLess(html.index("HB-HIGHHI"), html.index("HB-LOWLOW"))

    def test_officer_list_shows_no_identities(self):
        self.client.login(username="sarah", password="pw")
        self.assertNotContains(self.client.get("/officer/"), "abc123secretpseudo0")


class SeedDemoTests(TestCase):
    def test_seed_creates_partners_officers_and_groups(self):
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Partner.objects.count(), 5)
        self.assertEqual(Officer.objects.count(), 6)
        self.assertEqual(
            set(Group.objects.values_list("name", flat=True)),
            {"officer", "supervisor", "safeguarding", "admin"},
        )

    def test_seed_can_run_twice(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Partner.objects.count(), 5)
        self.assertEqual(Officer.objects.count(), 6)
