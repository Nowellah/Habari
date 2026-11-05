from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from channels.gateway import handle, handle_voice_transcript
from channels.telegram import TelegramBot
from core.models import Case


class VoiceConfirmTests(TestCase):
    """A voice note is never sent until the child has seen the words (A13)."""

    def test_transcript_is_shown_for_confirmation_first(self):
        handle("telegram", "tg:9", "/start")
        handle("telegram", "tg:9", "2")
        out = handle_voice_transcript("telegram", "tg:9", "he wants my pictures")
        self.assertIn("he wants my pictures", out["reply_text"])
        self.assertEqual(out["state"], "VOICE_CONFIRM")
        self.assertFalse(Case.objects.exists())

    def test_yes_sends_the_transcript_as_if_typed(self):
        handle("telegram", "tg:9", "/start")
        handle("telegram", "tg:9", "2")
        handle_voice_transcript("telegram", "tg:9", "he wants my pictures")
        out = handle("telegram", "tg:9", "1")
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(case.messages.get().text, "he wants my pictures")
        self.assertIn("via_voice", case.flags)

    def test_typing_instead_replaces_the_transcript(self):
        handle("telegram", "tg:9", "/start")
        handle("telegram", "tg:9", "2")
        handle_voice_transcript("telegram", "tg:9", "he wants my picture frames")
        out = handle("telegram", "tg:9", "he wants my nude pictures")
        case = Case.objects.get(code=out["case_code"])
        self.assertEqual(case.messages.get().text, "he wants my nude pictures")

    def test_voice_note_as_first_message_goes_through_the_normal_flow(self):
        handle_voice_transcript("telegram", "tg:9", "I want to die")
        out = handle("telegram", "tg:9", "1")
        self.assertEqual(Case.objects.get(code=out["case_code"]).severity, 4)


class FakeTelegram:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[-1], json))

        class R:
            def json(self_inner):
                return {"ok": True, "result": {"file_path": "voice/file_1.oga"}}
        return R()

    def get(self, url, params=None, timeout=None):
        class R:
            status_code = 200
            content = b"OggS-fake-audio"
        return R()

    def texts(self):
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


class TelegramVoiceTests(TestCase):
    def voice_update(self):
        return {"update_id": 1, "message": {"chat": {"id": 9}, "voice": {"file_id": "abc", "duration": 4}}}

    def test_voice_note_is_transcribed_and_shown_back(self):
        tg = FakeTelegram()
        with patch("core.ai_client.transcribe", return_value={"text": "he wants my pictures", "language": "en"}):
            TelegramBot("T", session=tg).handle_update(self.voice_update())
        self.assertIn("he wants my pictures", tg.texts()[-1])

    def test_no_speech_engine_asks_child_to_type(self):
        tg = FakeTelegram()
        with patch("core.ai_client.transcribe", return_value=None):
            TelegramBot("T", session=tg).handle_update(self.voice_update())
        self.assertIn("type", tg.texts()[-1])


class VoiceApiTests(TestCase):
    def post(self):
        audio = SimpleUploadedFile("note.webm", b"fake-audio", content_type="audio/webm")
        return self.client.post("/api/voice/transcribe", {"audio": audio, "language": "en"})

    def test_transcript_comes_back_for_the_child_to_check(self):
        with patch("core.ai_client.transcribe", return_value={"text": "someone is threatening me", "language": "en"}):
            r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], "someone is threatening me")

    def test_no_engine_asks_child_to_type(self):
        with patch("core.ai_client.transcribe", return_value=None):
            r = self.post()
        self.assertEqual(r.status_code, 503)
        self.assertIn("type", r.json()["message"])

    def test_chosen_language_is_passed_to_the_speech_service(self):
        with patch("core.ai_client.transcribe", return_value={"text": "x", "language": "lg"}) as mocked:
            audio = SimpleUploadedFile("voice.wav", b"RIFF", content_type="audio/wav")
            self.client.post("/api/voice/transcribe", {"audio": audio, "language": "lg"})
        self.assertEqual(mocked.call_args.args[2], "lg")

    def test_unknown_language_is_not_passed_on(self):
        with patch("core.ai_client.transcribe", return_value={"text": "x"}) as mocked:
            audio = SimpleUploadedFile("voice.wav", b"RIFF", content_type="audio/wav")
            self.client.post("/api/voice/transcribe", {"audio": audio, "language": "<script>"})
        self.assertIsNone(mocked.call_args.args[2])

    def test_chat_page_offers_a_language_choice_and_read_aloud(self):
        page = self.client.get("/chat")
        self.assertContains(page, 'id="voice-lang"')
        self.assertContains(page, 'value="lg"')
        self.assertContains(page, 'id="read-aloud"')

    def test_missing_audio_is_rejected(self):
        self.assertEqual(self.client.post("/api/voice/transcribe", {}).status_code, 400)

    def test_chat_page_has_a_speak_button(self):
        self.assertContains(self.client.get("/chat"), 'id="speak"')

    def test_voice_shortcut_opens_the_chat(self):
        r = self.client.get("/voice")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/chat?voice=1", r["Location"])
