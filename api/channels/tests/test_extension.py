import base64
import json
import shutil
import tempfile

from django.test import TestCase, override_settings

from core.evidence import verify_chain
from core.models import Case

# 1x1 transparent PNG
PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002"
    "000154a24f5d0000000049454e44ae426082")).decode()
META = {"url": "https://www.instagram.com/p/abc", "platform": "instagram", "title": "Post by @stranger"}


class ExtensionEvidenceTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def send(self, text, meta=None):
        body = {"sender_id": "ext-123", "text": text, "meta": meta or {}}
        r = self.client.post("/api/channel/extension", json.dumps(body), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def report(self, meta):
        self.send("HELP", meta)
        self.send("2", meta)
        return Case.objects.get(code=self.send("someone wants my pictures", meta)["case_code"])

    def kinds(self, case):
        return sorted(case.evidence.values_list("kind", flat=True))

    def test_page_details_are_saved_as_evidence_once(self):
        case = self.report(META)
        self.assertEqual(self.kinds(case), ["page_title", "platform", "url"])
        self.assertTrue(verify_chain(case))

    def test_more_messages_with_the_same_page_add_nothing_new(self):
        case = self.report(META)
        self.send("he sent it again", META)
        self.assertEqual(case.evidence.count(), 3)

    def test_screenshot_is_saved_with_its_hash(self):
        case = self.report({**META, "screenshot": "data:image/png;base64," + PNG})
        shot = case.evidence.get(kind="screenshot")
        self.assertTrue(shot.value.startswith("sha256:"))
        self.assertIn("bytes:", shot.value)

    def test_non_image_screenshot_is_ignored(self):
        case = self.report({**META, "screenshot": "data:text/html;base64,PGgxPmhpPC9oMT4="})
        self.assertNotIn("screenshot", self.kinds(case))

    def test_oversized_screenshot_is_ignored(self):
        big = base64.b64encode(b"\x89PNG" + b"0" * (4 * 1024 * 1024)).decode()
        case = self.report({**META, "screenshot": "data:image/png;base64," + big})
        self.assertNotIn("screenshot", self.kinds(case))

    def test_only_web_links_are_kept(self):
        case = self.report({"url": "javascript:alert(1)", "platform": "instagram"})
        self.assertEqual(self.kinds(case), ["platform"])

    def test_no_meta_means_no_evidence(self):
        self.assertEqual(self.report({}).evidence.count(), 0)

    def test_screenshot_is_not_echoed_back(self):
        self.send("HELP", META)
        self.send("2", META)
        out = self.send("x", {**META, "screenshot": "data:image/png;base64," + PNG})
        self.assertNotIn("base64", json.dumps(out))
