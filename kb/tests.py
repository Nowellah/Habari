from django.test import TestCase

from core.tests.helpers import seed
from kb.library import articles, render_markdown, search


class LibraryTests(TestCase):
    def test_articles_load_with_title_audience_and_status(self):
        items = articles()
        self.assertGreaterEqual(len(items), 6)
        for a in items:
            self.assertTrue(a["title"])
            self.assertIn(a["audience"], {"child", "adult", "officer"})
            self.assertIn("status", a)

    def test_search_finds_the_right_article(self):
        results = search("someone wants me to send pictures and money")
        self.assertEqual(results[0]["slug"], "someone-wants-pictures")

    def test_search_by_audience(self):
        self.assertTrue(all(a["audience"] != "officer" for a in search("", audiences={"child", "adult"})))

    def test_markdown_is_escaped(self):
        html = render_markdown("# Title\n\n- one\n- two\n\n<script>alert(1)</script> **bold**")
        self.assertIn("<h2>Title</h2>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>bold</strong>", html)


class PagesTests(TestCase):
    def test_public_list_shows_child_articles_but_not_officer_procedures(self):
        r = self.client.get("/kb")
        self.assertContains(r, "What to do first")
        self.assertNotContains(r, "Officer procedure")

    def test_staff_see_officer_procedures(self):
        seed()
        self.client.login(username="sarah", password="habari-demo")
        self.assertContains(self.client.get("/kb"), "Officer procedure")

    def test_article_page(self):
        r = self.client.get("/kb/safe-first-steps")
        self.assertContains(r, "<li>")
        self.assertContains(r, "Needs review")

    def test_officer_article_is_hidden_from_the_public(self):
        self.assertEqual(self.client.get("/kb/officer-sextortion").status_code, 404)

    def test_unknown_article(self):
        self.assertEqual(self.client.get("/kb/nope").status_code, 404)

    def test_search_page(self):
        self.assertContains(self.client.get("/kb", {"q": "teacher"}), "Teachers: pointing a child to help")

    def test_chat_links_to_safety_tips(self):
        self.assertContains(self.client.get("/chat"), 'href="/kb"')
