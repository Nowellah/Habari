from django.test import TestCase


class WebChatPageTests(TestCase):
    def setUp(self):
        self.r = self.client.get("/chat")

    def test_page_loads(self):
        self.assertEqual(self.r.status_code, 200)

    def test_anonymous_mode_sets_no_cookies(self):
        self.assertEqual(len(self.r.cookies), 0)

    def test_nothing_is_saved_on_the_device(self):
        for store in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
            self.assertNotContains(self.r, store)

    def test_page_is_not_cached_by_the_browser(self):
        self.assertIn("no-store", self.r["Cache-Control"])

    def test_quick_exit_and_helpline_are_always_visible(self):
        self.assertContains(self.r, "Quick exit")
        self.assertContains(self.r, 'href="tel:116"')

    def test_friendly_entry_point(self):
        self.assertContains(self.r, "Talk to us")

    def test_talks_to_the_web_channel(self):
        self.assertContains(self.r, "/api/channel/web")
