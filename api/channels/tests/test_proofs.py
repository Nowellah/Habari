import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from channels import proofs
from channels.tests.test_gateway import GatewayTestCase
from core.evidence import verify_chain
from core.models import Case

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"\x00" * 64


class ProofBase(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

    def web(self, text, sender="web-p"):
        return self.send(text, sender=sender, channel="web")

    def upload(self, data=PNG, name="shot.png", sender="web-p"):
        return self.client.post("/api/proof", {"sender_id": sender, "file": SimpleUploadedFile(name, data)})

    def open_case(self):
        self.web("MENU")
        self.web("REPORT")
        self.web("5")
        return self.web("someone keeps sending me rude messages")


class ProofTests(ProofBase):
    def test_the_bot_asks_for_screenshots_after_the_feeling_question(self):
        self.open_case()
        out = self.web("1")
        self.assertIn("Do you have screenshots", out["reply_text"])
        self.assertIn("do not send private photos", out["reply_text"])
        self.assertEqual([o["key"] for o in out["options"]], ["PROOF_ADD", "PROOF_LATER"])

    def test_not_now_is_accepted_and_nothing_is_stored(self):
        self.open_case()
        self.web("1")
        out = self.web("PROOF_LATER")
        self.assertIn("later with the paperclip", out["reply_text"])
        self.assertEqual(Case.objects.get().messages.count(), 1)

    def test_a_screenshot_is_kept_on_the_case_in_the_evidence_chain(self):
        first = self.open_case()
        r = self.upload()
        self.assertEqual(r.status_code, 200)
        case = Case.objects.get(code=first["case_code"])
        items = proofs.for_case(case)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["is_image"])
        self.assertTrue(verify_chain(case))
        self.assertEqual([o["key"] for o in r.json()["options"]], ["PROOF_ADD", "PROOF_DONE"])

    def test_officer_can_open_it_and_a_stranger_cannot(self):
        first = self.open_case()
        self.upload()
        self.upload(PDF, "chat.pdf")
        case = Case.objects.get(code=first["case_code"])
        image, pdf = proofs.for_case(case)
        url = f"/officer/case/{case.code}/proof/{image['id']}"
        self.assertEqual(self.client.get(url).status_code, 302)  # sent to sign in
        User.objects.create_user("visitor", password="pw")
        self.client.login(username="visitor", password="pw")
        self.assertEqual(self.client.get(url).status_code, 403)
        User.objects.create_superuser("boss", password="pw")
        self.client.login(username="boss", password="pw")
        got = self.client.get(url)
        self.assertEqual((got.status_code, got["Content-Type"], got["X-Content-Type-Options"]), (200, "image/png", "nosniff"))
        self.assertEqual(b"".join(got.streaming_content), PNG)
        doc = self.client.get(f"/officer/case/{case.code}/proof/{pdf['id']}")
        self.assertIn("attachment", doc["Content-Disposition"])
        self.assertContains(self.client.get(f"/officer/case/{case.code}/"), "Proof from the child")

    def test_proof_path_refuses_anything_but_a_stored_file(self):
        for name in ("../secret.png", "proof/../x.png", "proof/abc.png", "/etc/passwd", f"proof/{'a' * 32}.exe"):
            with self.assertRaises(ValueError):
                proofs.file_path(name)

    def test_the_file_type_is_checked_from_its_content_not_its_name(self):
        self.open_case()
        r = self.upload(b"MZ" + b"\x00" * 100, "virus.png")
        self.assertEqual(r.status_code, 415)
        self.assertFalse(Case.objects.get().evidence.filter(kind=proofs.KIND).exists())

    def test_a_file_over_the_limit_is_refused(self):
        self.open_case()
        r = self.upload(PNG + b"\x00" * (proofs.MAX_BYTES + 1))
        self.assertEqual(r.status_code, 413)

    def test_without_a_case_the_file_is_not_kept(self):
        r = self.upload(sender="web-nobody")
        self.assertEqual(r.status_code, 200)
        self.assertIn("tell me what happened first", r.json()["reply_text"])
        self.assertFalse(Case.objects.exists())
        self.assertFalse(list(__import__("pathlib").Path(self.media).rglob("*.png")))

    def test_the_same_file_twice_is_two_entries_but_the_chain_holds(self):
        first = self.open_case()
        self.upload()
        self.upload()
        case = Case.objects.get(code=first["case_code"])
        self.assertEqual(len(proofs.for_case(case)), 2)
        self.assertTrue(verify_chain(case))


class CaseQuestionTests(GatewayTestCase):
    def web(self, text, sender="web-q"):
        return self.send(text, sender=sender, channel="web")

    def open_case(self):
        self.web("MENU")
        self.web("REPORT")
        self.web("5")
        self.web("someone keeps sending me rude messages")
        self.web("1")

    def test_what_do_i_do_now_gets_clear_steps_not_a_bare_thank_you(self):
        self.open_case()
        out = self.web("what do i do now")
        parts = out["reply_text"].split("\n\n")
        self.assertEqual(parts[0], "Here is what you can do now.")
        self.assertIn("Do not delete", out["reply_text"])
        self.assertIn("grown-up", out["reply_text"])
        self.assertNotIn("I added this", out["reply_text"])
        self.assertTrue(all(len(p) < 110 for p in parts))

    def test_steps_ask_for_screenshots_only_until_some_are_added(self):
        self.open_case()
        self.assertEqual([o["key"] for o in self.web("what do i do now")["options"]], ["PROOF_ADD", "PROOF_LATER"])

    def test_a_specific_question_gets_its_reviewed_answer(self):
        self.open_case()
        out = self.web("should I delete the chat?")
        self.assertNotIn("I added this", out["reply_text"])
        self.assertIn("Other copies may exist", out["reply_text"])

    def test_a_plain_statement_is_still_just_added(self):
        self.open_case()
        out = self.web("he also sent a picture")
        self.assertIn("I added this", out["reply_text"])


class ProofCheckTests(ProofBase):
    """The automatic check is a hint. It never blocks a file and never claims a picture is real."""

    def check(self, **kw):
        base = {"kind": "document", "relevant": "no", "sensitive": False, "reason": "Handwritten maths notes."}
        return patch("channels.gateway.ai_client.check_proof", return_value={**base, **kw})

    def test_a_picture_that_does_not_fit_is_kept_and_the_child_is_asked_gently(self):
        first = self.open_case()
        with self.check():
            r = self.upload()
        out = r.json()
        self.assertIn("could not see how this picture shows what you told me", out["reply_text"])
        self.assertNotIn("maths", out["reply_text"])
        self.assertEqual([o["key"] for o in out["options"]], ["PROOF_RIGHT", "PROOF_ADD"])
        case = Case.objects.get(code=first["case_code"])
        self.assertEqual(len(proofs.for_case(case)), 1)
        self.assertIn("proof_unclear", case.flags)
        self.assertTrue(verify_chain(case))

    def test_the_child_can_say_it_is_the_right_picture(self):
        self.open_case()
        with self.check():
            self.upload()
        self.assertIn("A helper will look at it.", self.web("PROOF_RIGHT")["reply_text"])

    def test_a_fitting_picture_gets_the_normal_reply(self):
        first = self.open_case()
        with self.check(kind="chat_screenshot", relevant="yes", reason="A chat."):
            out = self.upload().json()
        self.assertIn("I kept it for the helper", out["reply_text"])
        self.assertNotIn("proof_unclear", Case.objects.get(code=first["case_code"]).flags)

    def test_a_sensitive_picture_is_not_described_and_is_flagged(self):
        first = self.open_case()
        with self.check(relevant="yes", sensitive=True, reason="should not be echoed"):
            out = self.upload().json()
        self.assertIn("I will not look at it again", out["reply_text"])
        self.assertNotIn("echoed", out["reply_text"])
        self.assertIn("proof_sensitive", Case.objects.get(code=first["case_code"]).flags)

    def test_when_no_check_is_set_up_nothing_changes(self):
        first = self.open_case()
        out = self.upload().json()
        self.assertIn("I kept it for the helper", out["reply_text"])
        self.assertEqual(Case.objects.get(code=first["case_code"]).flags.count("proof_unclear"), 0)

    def test_the_officer_sees_the_check_with_a_warning_that_it_can_be_wrong(self):
        first = self.open_case()
        with self.check():
            self.upload()
        User.objects.create_superuser("boss", password="pw")
        self.client.login(username="boss", password="pw")
        page = self.client.get(f"/officer/case/{first['case_code']}/")
        self.assertContains(page, "may not match what the child reported")
        self.assertContains(page, "can be wrong")

    def test_a_pdf_is_never_sent_to_the_vision_model(self):
        self.open_case()
        env = {"HABARI_OLLAMA_URL": "http://127.0.0.1:11434", "HABARI_VISION_MODEL": "m"}
        with patch.dict("os.environ", env), patch("ai_service.vision.requests.post") as post:
            out = self.upload(PDF, "chat.pdf").json()
        post.assert_not_called()
        self.assertIn("I kept it for the helper", out["reply_text"])
