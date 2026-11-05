import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.test import TestCase

from channels.meta_evidence import attach_meta
from core.tests.helpers import make_case


class InstallableAppTests(TestCase):
    def test_manifest_has_share_target_and_shortcuts(self):
        r = self.client.get("/manifest.webmanifest")
        self.assertEqual(r.status_code, 200)
        self.assertIn("manifest+json", r["Content-Type"])
        m = json.loads(r.content)
        self.assertEqual(m["share_target"]["action"], "/share")
        self.assertEqual(set(m["share_target"]["params"]), {"title", "text", "url"})
        self.assertIn("/chat?quick=1", [s["url"] for s in m["shortcuts"]])
        self.assertIn("/voice", [s["url"] for s in m["shortcuts"]])

    def test_icons_exist(self):
        m = json.loads(self.client.get("/manifest.webmanifest").content)
        sizes = {i["sizes"] for i in m["icons"]}
        self.assertTrue({"192x192", "512x512"} <= sizes)
        for icon in m["icons"]:
            self.assertTrue((Path(settings.BASE_DIR) / icon["src"].lstrip("/")).exists(), icon["src"])

    def test_service_worker_caches_nothing(self):
        r = self.client.get("/sw.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r["Content-Type"])
        self.assertNotContains(r, "caches.open")

    def test_chat_page_links_the_manifest(self):
        self.assertContains(self.client.get("/chat"), 'rel="manifest"')


class ShareTests(TestCase):
    def query(self, response):
        self.assertEqual(response.status_code, 302)
        target = urlparse(response["Location"])
        self.assertEqual(target.path, "/chat")
        return {k: v[0] for k, v in parse_qs(target.query).items()}

    def test_shared_post_opens_the_chat_with_the_details(self):
        q = self.query(self.client.get("/share", {"title": "Post", "text": "look at this",
                                                  "url": "https://www.tiktok.com/@someone/video/1"}))
        self.assertEqual(q["shared"], "1")
        self.assertEqual(q["text"], "look at this")
        self.assertEqual(q["url"], "https://www.tiktok.com/@someone/video/1")

    def test_non_web_links_are_dropped(self):
        q = self.query(self.client.get("/share", {"url": "javascript:alert(1)", "text": "x"}))
        self.assertNotIn("url", q)

    def test_link_inside_shared_text_is_used(self):
        q = self.query(self.client.get("/share", {"text": "see https://www.instagram.com/p/abc please"}))
        self.assertEqual(q["url"], "https://www.instagram.com/p/abc")

    def test_embeddable_report_link(self):
        q = self.query(self.client.get("/r", {"src": "tiktok", "handle": "abc", "url": "https://www.tiktok.com/@abc"}))
        self.assertEqual(q["src"], "tiktok")
        self.assertEqual(q["handle"], "abc")

    def test_mock_social_feed_uses_the_report_link(self):
        r = self.client.get("/mock/social")
        self.assertContains(r, "I need a friend")
        self.assertContains(r, "/r?src=")


class SharedEvidenceTests(TestCase):
    def test_platform_is_worked_out_from_the_link(self):
        case = make_case()
        attach_meta(case, {"url": "https://www.tiktok.com/@someone", "handle": "@someone"})
        kinds = dict(case.evidence.values_list("kind", "value"))
        self.assertEqual(kinds["platform"], "tiktok")
        self.assertEqual(kinds["handle"], "@someone")
