"""
Unit tests for conversation history compaction (Option B).
"""

import unittest
from unittest.mock import MagicMock, patch
from agent.core.compaction import format_messages_for_compaction, compact_conversation_history


class TestConversationCompaction(unittest.TestCase):

    def setUp(self):
        self.sample_messages = [
            {"role": "system", "content": "You are Raven."},
            {"role": "user", "content": "Let's work on the user auth module."},
            {"role": "assistant", "content": "I will inspect src/auth.py.", "tool_calls": [{"function": {"name": "read_file", "arguments": "{\"file_path\": \"src/auth.py\"}"}}]},
            {"role": "tool", "name": "read_file", "content": "def authenticate(): pass"},
            {"role": "assistant", "content": "Auth file reviewed. Now let's implement login."},
            {"role": "user", "content": "Now add JWT verification."},
            {"role": "assistant", "content": "JWT verification added to src/auth.py."},
        ]

    def test_format_messages_for_compaction(self):
        transcript = format_messages_for_compaction(self.sample_messages[1:5])
        self.assertIn("USER:\nLet's work on the user auth module.", transcript)
        self.assertIn("ASSISTANT TOOL CALLS:\nread_file", transcript)
        self.assertIn("TOOL RESULT (read_file):\ndef authenticate(): pass", transcript)
        self.assertIn("Auth file reviewed.", transcript)

    def test_short_conversation_skips_compaction(self):
        short_msgs = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = compact_conversation_history(short_msgs)
        self.assertFalse(result["success"])
        self.assertIn("too short", result["error"].lower())

    @patch("agent.core.compaction.read_prompt_from_file")
    @patch("agent.core.llm.get_genai_client")
    def test_compact_conversation_history_option_b_success(self, mock_get_client, mock_read_prompt):
        mock_read_prompt.return_value = "Compaction prompt instructions."
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="## Distillation Summary\n- Implemented JWT in auth.py."))
        ]
        mock_client.chat.completions.create.return_value = mock_completion
        mock_get_client.return_value = mock_client

        result = compact_conversation_history(
            self.sample_messages,
            custom_instructions="Focus on security changes."
        )

        self.assertTrue(result["success"])
        self.assertIn("Distillation Summary", result["summary"])
        compacted = result["compacted_messages"]

        # Option B layout:
        # [0]: System prompt
        # [1]: Synthetic user with summary
        # [2]: Synthetic assistant acknowledgment
        # [-2:]: Preserved latest user + assistant turns
        self.assertEqual(compacted[0]["role"], "system")
        self.assertEqual(compacted[1]["role"], "user")
        self.assertIn("[Previous Conversation Context & Summary]", compacted[1]["content"])
        self.assertEqual(compacted[2]["role"], "assistant")

        # Verify preserved messages (last 2 non-system turns)
        self.assertEqual(compacted[-2], self.sample_messages[-2])
        self.assertEqual(compacted[-1], self.sample_messages[-1])

    @patch("agent.core.compaction.read_prompt_from_file")
    @patch("agent.core.llm.get_genai_client")
    def test_agent_chat_session_compact_history(self, mock_get_client, mock_read_prompt):
        mock_read_prompt.return_value = "Compaction prompt instructions."
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Summary of past turns."))
        ]
        mock_client.chat.completions.create.return_value = mock_completion
        mock_get_client.return_value = mock_client

        from agent.core.llm import AgentChatSession
        with patch.object(AgentChatSession, "__init__", lambda self, *args, **kwargs: None):
            session = AgentChatSession("test-model")
            session.model_name = "test-model"
            session.session_id = "test-session"
            session.session_title = "Test Session"
            session.messages = list(self.sample_messages)
            session.save_session_state = MagicMock()
            session.get_context_usage = MagicMock()

            res = session.compact_history(custom_instructions="focus on auth")
            self.assertTrue(res["success"])
            self.assertIn("tokens_before", res)
            self.assertIn("tokens_after", res)
            self.assertIn("savings", res)
            self.assertIn("percent", res)
            session.save_session_state.assert_called_once()
            session.get_context_usage.assert_called_once()


if __name__ == "__main__":
    unittest.main()
