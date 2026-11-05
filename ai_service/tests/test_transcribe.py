from unittest import TestCase

from fastapi.testclient import TestClient

from ai_service import speech
from ai_service.app import app

client = TestClient(app)


class TranscribeEndpointTests(TestCase):
    def tearDown(self):
        speech.reset_transcriber()

    def post(self, data=b"fake-audio", language=""):
        return client.post("/transcribe", files={"audio": ("note.ogg", data, "audio/ogg")},
                           data={"language": language})

    def test_no_speech_engine_says_so_clearly(self):
        speech.set_transcriber(None)
        r = self.post()
        self.assertEqual(r.status_code, 503)
        self.assertIn("type", r.json()["detail"])

    def test_transcript_is_returned(self):
        speech.set_transcriber(lambda audio, language: {"text": " he wants my pictures ", "language": "en"})
        r = self.post(language="en")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], "he wants my pictures")
        self.assertEqual(r.json()["language"], "en")

    def test_language_hint_is_passed_on(self):
        seen = {}
        def fake(audio, language):
            seen["language"] = language
            return {"text": "x", "language": language}
        speech.set_transcriber(fake)
        self.post(language="lg")
        self.assertEqual(seen["language"], "lg")

    def test_empty_audio_is_rejected(self):
        speech.set_transcriber(lambda a, l: {"text": "x"})
        self.assertEqual(self.post(data=b"").status_code, 400)

    def test_too_long_audio_is_rejected(self):
        speech.set_transcriber(lambda a, l: {"text": "x"})
        self.assertEqual(self.post(data=b"0" * (11 * 1024 * 1024)).status_code, 413)

    def test_engine_failure_is_503_not_a_crash(self):
        def broken(a, l):
            raise RuntimeError("model crashed")
        speech.set_transcriber(broken)
        self.assertEqual(self.post().status_code, 503)

    def test_health_reports_speech_engine(self):
        self.assertIn("speech_to_text", client.get("/health").json())
