import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from channels import voice_notes
from core.models import Case
from core.evidence import verify_chain

WAV = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x01" * 200


def upload(data=WAV):
    return SimpleUploadedFile("voice.wav", data, content_type="audio/wav")


class VoiceNoteTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

    def post(self, text="he keeps asking for my nude pictures", sender="web-a", **extra):
        with patch("channels.voice_views.ai_client.transcribe", return_value={"text": text, "language": "en"} if text else None):
            return self.client.post("/api/voice-note", {
                "sender_id": sender, "audio": upload(), "spoken": "en", "language": "en",
                "cues": '{"seconds": 24, "level": 14, "peak": 40, "pauses": 3}', **extra,
            })

    def test_bot_replies_and_the_recording_is_kept_on_the_case(self):
        r = self.post()
        self.assertEqual(r.status_code, 200)
        case = Case.objects.get(code=r.json()["case_code"])
        notes = voice_notes.for_case(case)
        self.assertEqual(len(notes), 1)
        self.assertIn("24 s long", notes[0]["cues"])
        self.assertIn("raised voice", notes[0]["cues"])
        self.assertTrue(verify_chain(case))
        self.assertEqual(case.messages.get().text, "he keeps asking for my nude pictures")

    def test_note_waits_until_a_case_exists(self):
        first = self.post(text="hello there my friend").json()
        self.assertFalse(Case.objects.exists())
        self.assertIsNone(first["case_code"])
        out = self.post(text="he keeps asking for my nude pictures").json()
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(len(voice_notes.for_case(case)), 2)

    def test_note_is_attached_only_once(self):
        out = self.post().json()
        self.client.post("/api/channel/web", {"sender_id": "web-a", "text": "ok"}, content_type="application/json")
        self.assertEqual(len(voice_notes.for_case(Case.objects.get(code=out["case_code"]))), 1)

    def test_unreadable_speech_still_keeps_the_audio(self):
        out = self.post(text="").json()
        self.assertEqual(out["state"], "PICK_HARM")

    def test_rejects_missing_sender_empty_and_non_wav_audio(self):
        self.assertEqual(self.client.post("/api/voice-note", {"audio": upload()}).status_code, 400)
        self.assertEqual(self.client.post("/api/voice-note", {"sender_id": "x"}).status_code, 400)
        bad = self.client.post("/api/voice-note", {"sender_id": "x", "audio": upload(b"not audio at all" * 10)})
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(Case.objects.exists())

    def test_cues_outside_the_range_are_ignored(self):
        self.assertEqual(voice_notes.clean_cues({"seconds": 99999, "level": "loud", "pauses": 2, "x": 1}), {"pauses": 2})
        self.assertEqual(voice_notes.clean_cues("nope"), {})

    def test_audio_path_refuses_anything_but_a_stored_note(self):
        for name in ("../secret.wav", "voice/../x.wav", "voice/abc.wav", "/etc/passwd"):
            with self.assertRaises(ValueError):
                voice_notes.audio_path(name)

    def test_officer_can_play_it_and_a_stranger_cannot(self):
        code = self.post().json()["case_code"]
        evidence = Case.objects.get(code=code).evidence.get(kind="voice_note")
        url = f"/officer/case/{code}/voice/{evidence.id}"
        self.assertEqual(self.client.get(url).status_code, 302)  # sent to sign in
        User.objects.create_user("visitor", password="pw")
        self.client.login(username="visitor", password="pw")
        self.assertEqual(self.client.get(url).status_code, 403)
        User.objects.create_superuser("boss", password="pw")
        self.client.login(username="boss", password="pw")
        got = self.client.get(url)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got["Content-Type"], "audio/wav")
        self.assertEqual(b"".join(got.streaming_content), WAV)
        page = self.client.get(f"/officer/case/{code}/")
        self.assertContains(page, "Voice notes")
        self.assertContains(page, f"/officer/case/{code}/voice/{evidence.id}")
