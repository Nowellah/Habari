from unittest import TestCase

from ai_service import speech
from core import ai_client


class TranscribeTests(TestCase):
    def tearDown(self):
        speech.reset_transcriber()

    def test_no_speech_engine_returns_none(self):
        speech.set_transcriber(None)
        self.assertIsNone(ai_client.transcribe(b"fake-audio", "note.ogg"))

    def test_transcript_is_returned_trimmed(self):
        speech.set_transcriber(lambda audio, language: {"text": " he wants my pictures ", "language": "en"})
        out = ai_client.transcribe(b"fake-audio", "note.ogg", "en")
        self.assertEqual(out["text"], "he wants my pictures")
        self.assertEqual(out["language"], "en")

    def test_language_hint_is_passed_on(self):
        seen = {}

        def fake(audio, language):
            seen["language"] = language
            return {"text": "x", "language": language}

        speech.set_transcriber(fake)
        ai_client.transcribe(b"fake-audio", "note.ogg", "lg")
        self.assertEqual(seen["language"], "lg")

    def test_empty_audio_returns_none(self):
        speech.set_transcriber(lambda a, l: {"text": "x"})
        self.assertIsNone(ai_client.transcribe(b"", "note.ogg"))

    def test_engine_failure_returns_none_not_a_crash(self):
        def broken(a, l):
            raise RuntimeError("model crashed")

        speech.set_transcriber(broken)
        self.assertIsNone(ai_client.transcribe(b"fake-audio", "note.ogg"))

    def test_blank_transcript_returns_none(self):
        speech.set_transcriber(lambda a, l: {"text": "   "})
        self.assertIsNone(ai_client.transcribe(b"fake-audio", "note.ogg"))
