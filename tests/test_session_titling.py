"""
Unit tests for AI session titling and terminal tab title sync (US-SESSION-001 & US-SESSION-002).
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from agent.core.llm import generate_ai_session_title, AgentChatSession
from agent.terminal_ui.app import RavenTUI


class TestSessionTitling(unittest.TestCase):

    @patch("agent.core.llm.get_genai_client")
    def test_generate_ai_session_title_primary_model(self, mock_get_client):
        """Primary model (gemini-2.5-flash-lite) should be called first."""
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '"Docker Container Setup."'
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        title = generate_ai_session_title("How do I setup multi-stage docker build for python?")
        self.assertEqual(title, "Docker Container Setup")

        # Verify model used had gemini-2.5-flash-lite
        call_model = mock_client.chat.completions.create.call_args[1]["model"]
        self.assertIn("gemini-2.5-flash-lite", call_model)

    @patch("agent.core.llm.get_genai_client")
    def test_generate_ai_session_title_fallback_model(self, mock_get_client):
        """If primary model throws an exception, it should fallback to active model."""
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "FastAPI Authentication"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        # First call fails, second call succeeds
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("404 Model Not Found"),
            mock_resp
        ]
        mock_get_client.return_value = mock_client

        title = generate_ai_session_title(
            "Implement JWT auth with FastAPI",
            fallback_model="openai/gpt-4o"
        )
        self.assertEqual(title, "FastAPI Authentication")
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

        # Verify fallback call used active model
        second_call_model = mock_client.chat.completions.create.call_args_list[1][1]["model"]
        self.assertEqual(second_call_model, "openai/gpt-4o")

    @patch("agent.core.llm.get_genai_client")
    def test_generate_ai_session_title_all_fail_fallback_query(self, mock_get_client):
        """If all models fail, title falls back to sanitized query string."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Network error")
        mock_get_client.return_value = mock_client

        title = generate_ai_session_title("Analyze memory leak in Node.js application")
        self.assertIn("Analyze memory leak", title)
        self.assertLessEqual(len(title), 36)

    def test_update_session_title_persists(self):
        """AgentChatSession.update_session_title must update title and persist."""
        temp_dir = tempfile.TemporaryDirectory()
        with patch("agent.core.session_manager.get_sessions_dir", return_value=Path(temp_dir.name)):
            with patch("agent.core.llm.get_active_session_id", return_value=None):
                sess = AgentChatSession("gpt-4o", session_id="test_title_sess")
                sess.messages = [
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "hello"}
                ]
                sess.update_session_title("Refactored Database Schema")
                self.assertEqual(sess.session_title, "Refactored Database Schema")

                # Verify persistence
                from agent.core.session_manager import load_session
                saved = load_session("test_title_sess")
                self.assertIsNotNone(saved)
                self.assertEqual(saved["title"], "Refactored Database Schema")
        temp_dir.cleanup()

    @patch("agent.terminal_ui.app.set_terminal_title")
    def test_terminal_tab_title_sync(self, mock_set_title):
        """RavenTUI.update_status_bar must synchronize terminal window/tab title."""
        app = RavenTUI()
        app.chat_session = MagicMock()
        app.chat_session.session_title = "Kubernetes Helm Deployment"
        app.query_one = MagicMock()

        app.update_status_bar()

        self.assertEqual(app.title, "Raven - Kubernetes Helm Deployment")
        mock_set_title.assert_called_with("Raven - Kubernetes Helm Deployment")

    @patch("ctypes.windll.kernel32.SetConsoleTitleW")
    @patch("os.write")
    def test_set_terminal_title_win32_and_ansi(self, mock_os_write, mock_set_console):
        """set_terminal_title should invoke Win32 API and low-level fd write."""
        from agent.utils import set_terminal_title
        set_terminal_title("Raven - Test Title")

        mock_set_console.assert_called_with("Raven - Test Title")
        mock_os_write.assert_called()


if __name__ == "__main__":
    unittest.main()
