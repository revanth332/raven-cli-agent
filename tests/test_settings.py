import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import json
import os

from agent.core.settings import Settings


class TestSettingsPrecedence(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_env_takes_precedence_over_config(self):
        """Environment variables must take precedence over config.json values."""
        self.config_path.write_text(json.dumps({
            "RAVEN_MODEL": "config-model",
            "SMALL_MODEL": "config-small-model",
            "EMBEDDING_MODEL": "config-embed-model"
        }), encoding="utf-8")

        env_overrides = {
            "RAVEN_MODEL": "env-model",
            "MODEL": "env-model",
            "SMALL_MODEL": "env-small-model",
            "RAVEN_SMALL_MODEL": "env-small-model",
            "RAVEN_EMBEDDING_MODEL": "env-embed-model",
            "EMBEDDING_MODEL": "env-embed-model"
        }

        with patch.dict(os.environ, env_overrides, clear=False):
            with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
                s = Settings()
                s.config_file = self.config_path
                s.reload()

                self.assertEqual(s.RAVEN_MODEL, "env-model")
                self.assertEqual(s.MODEL, "env-model")
                self.assertEqual(s.RAVEN_SMALL_MODEL, "env-small-model")
                self.assertEqual(s.SMALL_MODEL, "env-small-model")
                self.assertEqual(s.RAVEN_EMBEDDING_MODEL, "env-embed-model")
                self.assertEqual(s.EMBEDDING_MODEL, "env-embed-model")

    def test_config_takes_precedence_when_no_env(self):
        """Config file values must be used when environment variables are absent."""
        self.config_path.write_text(json.dumps({
            "SMALL_MODEL": "config-small-model",
            "EMBEDDING_MODEL": "config-embed-model",
            "MODEL": "config-custom-model"
        }), encoding="utf-8")

        # Ensure env vars are not set
        clean_env = {
            "RAVEN_SMALL_MODEL": "",
            "SMALL_MODEL": "",
            "RAVEN_EMBEDDING_MODEL": "",
            "EMBEDDING_MODEL": "",
            "RAVEN_MODEL": "",
            "MODEL": "",
        }

        with patch.dict(os.environ, clean_env, clear=False):
            with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
                s = Settings()
                s.config_file = self.config_path
                s.reload()

                self.assertEqual(s.RAVEN_SMALL_MODEL, "config-small-model")
                self.assertEqual(s.SMALL_MODEL, "config-small-model")
                self.assertEqual(s.RAVEN_EMBEDDING_MODEL, "config-embed-model")
                self.assertEqual(s.EMBEDDING_MODEL, "config-embed-model")
                self.assertEqual(s.RAVEN_MODEL, "config-custom-model")
                self.assertEqual(s.MODEL, "config-custom-model")

    def test_default_fallback_when_neither_env_nor_config(self):
        """Defaults must apply when neither env nor config file defines the setting."""
        self.config_path.write_text("{}", encoding="utf-8")

        clean_env = {
            "RAVEN_SMALL_MODEL": "",
            "SMALL_MODEL": "",
            "RAVEN_EMBEDDING_MODEL": "",
            "EMBEDDING_MODEL": "",
            "RAVEN_MODEL": "",
            "MODEL": "",
        }

        with patch.dict(os.environ, clean_env, clear=False):
            with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
                s = Settings()
                s.config_file = self.config_path
                s.reload()

                self.assertIsNone(s.RAVEN_SMALL_MODEL)
                self.assertIsNone(s.SMALL_MODEL)
                self.assertIsNone(s.RAVEN_EMBEDDING_MODEL)
                self.assertIsNone(s.EMBEDDING_MODEL)
                self.assertEqual(s.RAVEN_MODEL, "google/gemini-3-flash-preview")
                self.assertEqual(s.MODEL, "google/gemini-3-flash-preview")

    def test_agent_budget_defaults_and_integer_coercion(self):
        clean_env = {
            "RAVEN_AGENT_SOFT_TURNS": "",
            "AGENT_SOFT_TURNS": "",
            "RAVEN_AGENT_HARD_TURNS": "",
            "AGENT_HARD_TURNS": "",
            "RAVEN_AGENT_MAX_TOOL_CALLS": "",
            "AGENT_MAX_TOOL_CALLS": "",
            "RAVEN_AGENT_MAX_NO_PROGRESS": "",
            "AGENT_MAX_NO_PROGRESS": "",
            "RAVEN_AGENT_GRACE_TURNS": "",
            "AGENT_GRACE_TURNS": "",
        }
        with patch.dict(os.environ, clean_env, clear=False):
            with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
                s = Settings()
                s.config_file = self.config_path
                s.reload()
                self.assertEqual(s.RAVEN_AGENT_SOFT_TURNS, 10)
                self.assertEqual(s.RAVEN_AGENT_HARD_TURNS, 20)
                self.assertEqual(s.RAVEN_AGENT_MAX_TOOL_CALLS, 40)
                self.assertEqual(s.RAVEN_AGENT_MAX_NO_PROGRESS, 3)
                self.assertEqual(s.RAVEN_AGENT_GRACE_TURNS, 2)

        with patch.dict(os.environ, {"RAVEN_AGENT_SOFT_TURNS": "12"}, clear=False):
            with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
                s = Settings()
                self.assertEqual(s.RAVEN_AGENT_SOFT_TURNS, 12)

    def test_type_coercion_boolean(self):
        """Boolean settings from strings in env or config should be properly coerced."""
        with patch.dict(os.environ, {"RAVEN_AUTO_APPROVE": "true", "RAVEN_USE_VERTEX_AI": "false"}):
            with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
                s = Settings()
                s.config_file = self.config_path
                s.reload()

                self.assertIs(s.RAVEN_AUTO_APPROVE, True)
                self.assertIs(s.AUTO_APPROVE, True)
                self.assertIs(s.RAVEN_USE_VERTEX_AI, False)
                self.assertIs(s.USE_VERTEX_AI, False)

    def test_set_config_updates_attributes_and_file(self):
        """set_config must update both internal attributes and disk JSON."""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir.name)):
            s = Settings()
            s.config_file = self.config_path
            s.set_config({
                "SMALL_MODEL": "test-small",
                "EMBEDDING_MODEL": "test-embed",
                "RAVEN_AUTO_APPROVE": True
            })

            self.assertEqual(s.RAVEN_SMALL_MODEL, "test-small")
            self.assertEqual(s.SMALL_MODEL, "test-small")
            self.assertEqual(s.RAVEN_EMBEDDING_MODEL, "test-embed")
            self.assertEqual(s.EMBEDDING_MODEL, "test-embed")
            self.assertIs(s.RAVEN_AUTO_APPROVE, True)

            # Check file on disk
            saved_json = json.loads(self.config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_json["SMALL_MODEL"], "test-small")
            self.assertEqual(saved_json["EMBEDDING_MODEL"], "test-embed")
            self.assertEqual(saved_json["RAVEN_AUTO_APPROVE"], True)


if __name__ == "__main__":
    unittest.main()
