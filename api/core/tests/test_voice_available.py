from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from core import ai_client


def health(body, status=200):
    response = MagicMock(status_code=status)
    response.json.return_value = body
    return response


class VoiceAvailableTests(TestCase):
    def test_true_when_an_engine_is_listed(self):
        with patch("requests.get", return_value=health({"speech_to_text": ["sunbird"]})):
            self.assertTrue(ai_client.voice_available())

    def test_false_when_no_engine_is_set_up(self):
        with patch("requests.get", return_value=health({"speech_to_text": []})):
            self.assertFalse(ai_client.voice_available())

    def test_false_when_the_service_is_down_or_odd(self):
        with patch("requests.get", side_effect=requests.ConnectionError()):
            self.assertFalse(ai_client.voice_available())
        with patch("requests.get", return_value=health({}, status=500)):
            self.assertFalse(ai_client.voice_available())
        with patch("requests.get", return_value=health(["not", "a", "dict"])):
            self.assertFalse(ai_client.voice_available())
