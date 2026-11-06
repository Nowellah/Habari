from unittest import TestCase
from unittest.mock import patch

from core import ai_client


class VoiceAvailableTests(TestCase):
    def test_true_when_an_engine_is_listed(self):
        with patch("core.ai_client.speech.engines_available", return_value=["sunbird"]):
            self.assertTrue(ai_client.voice_available())

    def test_false_when_no_engine_is_set_up(self):
        with patch("core.ai_client.speech.engines_available", return_value=[]):
            self.assertFalse(ai_client.voice_available())
