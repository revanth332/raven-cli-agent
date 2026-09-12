"""
Unit tests for multimodal session serialization and token accounting (US-IMAGE-003).
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import json

from agent.core.token_counter import count_tokens
from agent.core.session_manager import (
    create_session,
    save_session,
    load_session,
)
from agent.terminal_ui.chat_message import ChatMessageWidget


class TestMultimodalSession(unittest.TestCase):

    def test_multimodal_token_counting_capped(self):
        """Token count for image_url must not inflate with massive base64 strings."""
        large_b64 = "A" * 100000  # 100KB string
        content = [
            {"type": "text", "text": "What does this code do?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{large_b64}"}}
        ]
        msg = {"role": "user", "content": content}

        tokens = count_tokens(msg, "gpt-4o")
        # Text is ~6 tokens, image is ~1000 tokens, overhead is 4. Total should be ~1010-1020, NOT 25,000!
        self.assertLess(tokens, 1500)
        self.assertGreater(tokens, 900)

    def test_session_serialization_with_multimodal(self):
        """Sessions containing multimodal messages must serialize and deserialize properly."""
        temp_dir = tempfile.TemporaryDirectory()
        with patch("agent.core.session_manager.get_sessions_dir", return_value=Path(temp_dir.name)):
            sess = create_session(model_name="google/gemini-2.5-flash", session_id="test_m1")
            content = [
                {"type": "text", "text": "Inspect this screenshot"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,dGVzdA=="}}
            ]
            sess["messages"] = [
                {"role": "user", "content": content},
                {"role": "assistant", "content": "I see an error in your code."}
            ]
            save_session(sess, force=True)

            loaded = load_session("test_m1")
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded["messages"]), 2)
            self.assertEqual(loaded["messages"][0]["content"][0]["text"], "Inspect this screenshot")
        temp_dir.cleanup()

    def test_chat_message_widget_multimodal_badge(self):
        """ChatMessageWidget should extract and display an image badge for multimodal messages."""
        content = [
            {"type": "text", "text": "Fix this layout"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}
        ]
        widget = ChatMessageWidget(role="user", raw_text=content)
        self.assertEqual(widget.image_badge, "Attached Image")
        self.assertEqual(widget.raw_text, "Fix this layout")

    def test_chat_message_widget_strips_rich_markup_tags(self):
        """Legacy or raw rich markup tags should be parsed into image_badge rather than leaking into raw_text."""
        raw = "[bold #06B6D4][🖼️ Clipboard Screenshot (290x142)][/bold #06B6D4]\n\nWhat is this error?"
        widget = ChatMessageWidget(role="user", raw_text=raw)
        self.assertEqual(widget.image_badge, "Clipboard Screenshot (290x142)")
        self.assertEqual(widget.raw_text, "What is this error?")
        self.assertNotIn("[bold #06B6D4]", widget.raw_text)


if __name__ == "__main__":
    unittest.main()
