import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings


class WebAppConfigTests(TestCase):
    def test_config_gives_the_helpline_and_is_not_cached(self):
        with patch("core.ai_client.voice_available", return_value=False):
            r = self.client.get("/api/config")
        self.assertEqual(r.json(), {"helpline": "116", "voice": False})
        self.assertIn("no-store", r["Cache-Control"])

    def test_config_says_when_voice_is_set_up(self):
        with patch("core.ai_client.voice_available", return_value=True):
            self.assertTrue(self.client.get("/api/config").json()["voice"])

    @override_settings(HELPLINE_NUMBER="999")
    def test_config_follows_the_setting(self):
        with patch("core.ai_client.voice_available", return_value=False):
            self.assertEqual(self.client.get("/api/config").json()["helpline"], "999")


class BuiltWebAppTests(TestCase):
    def setUp(self):
        self.dist = Path(tempfile.mkdtemp())
        (self.dist / "assets").mkdir()
        (self.dist / "index.html").write_text("<div id=root>React app</div>", encoding="utf8")
        (self.dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf8")
        (self.dist.parent / "secret.txt").write_text("secret", encoding="utf8")

    def test_the_chat_route_serves_the_built_app_without_caching(self):
        with override_settings(WEB_DIST=self.dist):
            r = self.client.get("/chat")
        self.assertContains(r, "React app")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertEqual(len(r.cookies), 0)

    def test_without_a_build_the_django_page_is_served(self):
        with override_settings(WEB_DIST=self.dist / "missing"):
            self.assertContains(self.client.get("/chat"), "Talk to us")

    def test_assets_are_served(self):
        with override_settings(WEB_DIST=self.dist):
            r = self.client.get("/assets/app.js")
        self.assertEqual(r.status_code, 200)

    def test_assets_cannot_escape_the_assets_folder(self):
        with override_settings(WEB_DIST=self.dist):
            for path in ("/assets/../index.html", "/assets/..%2Fsecret.txt", "/assets/../../secret.txt"):
                with self.subTest(path):
                    self.assertIn(self.client.get(path).status_code, (400, 404))

    def test_assets_are_not_served_when_there_is_no_build(self):
        self.assertEqual(self.client.get("/assets/app.js").status_code, 404)
