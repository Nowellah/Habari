import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from ai_service.app import load_env


class LoadEnvTests(TestCase):
    def test_keys_in_the_env_file_reach_the_ai_service(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUNBIRD_TEST_KEY", None)
            path = Path(folder) / ".env"
            path.write_text("SUNBIRD_TEST_KEY=from-file\n", encoding="utf8")
            load_env(path)
            self.assertEqual(os.environ["SUNBIRD_TEST_KEY"], "from-file")
            os.environ.pop("SUNBIRD_TEST_KEY", None)

    def test_a_real_environment_variable_wins_over_the_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"SUNBIRD_TEST_KEY": "from-shell"}):
            path = Path(folder) / ".env"
            path.write_text("SUNBIRD_TEST_KEY=from-file\n", encoding="utf8")
            load_env(path)
            self.assertEqual(os.environ["SUNBIRD_TEST_KEY"], "from-shell")

    def test_a_missing_env_file_is_fine(self):
        load_env(Path("/nonexistent/.env"))
