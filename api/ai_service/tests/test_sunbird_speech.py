from unittest import TestCase
from unittest.mock import MagicMock, patch

from ai_service import speech, sunbird_client


class AudioPartTests(TestCase):
    def test_format_is_taken_from_the_first_bytes(self):
        cases = {
            b"RIFF\x00\x00\x00\x00WAVEfmt ": ("voice.wav", "audio/wav"),
            b"OggS\x00\x02": ("voice.ogg", "audio/ogg"),
            b"ID3\x04\x00": ("voice.mp3", "audio/mpeg"),
            b"\x00\x00\x00\x18ftypM4A ": ("voice.m4a", "audio/mp4"),
            b"\x1a\x45\xdf\xa3\x01": ("voice.webm", "audio/webm"),
        }
        for head, expected in cases.items():
            with self.subTest(expected):
                self.assertEqual(sunbird_client.audio_part(head), expected)

    def test_unknown_bytes_fall_back_to_ogg(self):
        self.assertEqual(sunbird_client.audio_part(b"???"), ("voice.ogg", "audio/ogg"))
        self.assertEqual(sunbird_client.audio_part(b""), ("voice.ogg", "audio/ogg"))


class LanguageTests(TestCase):
    def test_habari_codes_become_sunbird_codes(self):
        for habari, sunbird in (("en", "eng"), ("lg", "lug"), ("rn", "nyn"), ("sw", "swa")):
            self.assertEqual(sunbird_client.stt_language(habari), sunbird)

    def test_missing_or_unknown_language_still_names_one(self):
        for value in (None, "", "unknown", "xx"):
            self.assertEqual(sunbird_client.stt_language(value), "eng")


class TranscribeCallTests(TestCase):
    def call(self, response=None, error=None, token="t"):
        with patch.dict("os.environ", {"SUNBIRD_TOKEN": token}), patch("requests.post") as post:
            if error:
                post.side_effect = error
            else:
                post.return_value = response
            out = sunbird_client.transcribe(b"RIFF\x00\x00\x00\x00WAVEdata", "lg")
        return out, post

    def test_request_carries_audio_and_language(self):
        response = MagicMock()
        response.json.return_value = {"audio_transcription": "nze nfunye"}
        out, post = self.call(response)
        self.assertEqual(out, "nze nfunye")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["data"], {"language": "lug"})
        self.assertEqual(kwargs["files"]["audio"][0], "voice.wav")
        self.assertEqual(kwargs["files"]["audio"][2], "audio/wav")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer t"})

    def test_no_token_means_no_call(self):
        out, post = self.call(token="")
        self.assertIsNone(out)
        post.assert_not_called()

    def test_network_failure_returns_none(self):
        import requests
        out, _ = self.call(error=requests.ConnectionError("down"))
        self.assertIsNone(out)

    def test_empty_transcription_returns_none(self):
        response = MagicMock()
        response.json.return_value = {"audio_transcription": ""}
        out, _ = self.call(response)
        self.assertIsNone(out)


class EngineOrderTests(TestCase):
    def test_sunbird_is_tried_first_for_every_language_then_whisper(self):
        calls = []
        with patch.dict("os.environ", {"SUNBIRD_TOKEN": "t", "AI_WHISPER_MODEL": "tiny"}), \
                patch.object(speech, "_sunbird_transcribe", side_effect=lambda a, l: calls.append("sunbird")), \
                patch.object(speech, "_whisper_transcribe", side_effect=lambda a, l: calls.append("whisper") or {"text": "hi"}):
            out = speech.get_transcriber()(b"x", "en")
        self.assertEqual(calls, ["sunbird", "whisper"])
        self.assertEqual(out["text"], "hi")


class FailureLoggingTests(TestCase):
    def test_a_refused_request_is_logged_with_its_status_but_no_secrets(self):
        import requests
        response = MagicMock(status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        with patch.dict("os.environ", {"SUNBIRD_TOKEN": "secret-token"}), patch("requests.post", return_value=response):
            with self.assertLogs("ai_service.sunbird_client", level="WARNING") as logs:
                self.assertIsNone(sunbird_client.transcribe(b"RIFF....WAVE", "en"))
        self.assertIn("HTTP 401", logs.output[0])
        self.assertNotIn("secret-token", logs.output[0])
