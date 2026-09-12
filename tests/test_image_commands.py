"""
Unit tests for /image and /paste-image slash command integration (US-IMAGE-004).
"""

import unittest
from unittest.mock import patch, MagicMock
from agent.terminal_ui.app import SLASH_COMMANDS, RavenTUI
from agent.terminal_ui.chat_input import ChatInput


class TestImageCommands(unittest.TestCase):

    def test_slash_commands_registered(self):
        """Ensure /image and /paste-image are registered in SLASH_COMMANDS."""
        self.assertIn("/image", SLASH_COMMANDS)
        self.assertIn("/paste-image", SLASH_COMMANDS)
        self.assertIn("local image", SLASH_COMMANDS["/image"]["description"].lower())
        self.assertIn("screenshot", SLASH_COMMANDS["/paste-image"]["description"].lower())

    @patch("agent.terminal_ui.app.encode_image_file")
    def test_image_command_invalid_path(self, mock_encode):
        """Verify error handling when /image is given a non-existent file."""
        mock_encode.return_value = {"success": False, "error": "File does not exist."}

        app = RavenTUI()
        app.pending_permission = False
        app.chat_session = MagicMock()
        app.is_generating = False

        event = MagicMock()
        event.value = "/image nonexistent.png What is this?"
        event.text_area = MagicMock()

        # Mount mock history
        history_mock = MagicMock()
        app.query_one = MagicMock(return_value=history_mock)
        app.scroll_to_bottom = MagicMock()

        app.on_chat_input_submitted(event)

        # Should have mounted an error card
        history_mock.mount.assert_called()
        mounted_card = history_mock.mount.call_args[0][0]
        self.assertIn("Error Loading Image", mounted_card.raw_text)

    @patch("agent.terminal_ui.app.grab_clipboard_image")
    def test_paste_image_command_empty_clipboard(self, mock_grab):
        """Verify error handling when /paste-image has no clipboard image."""
        mock_grab.return_value = {"success": False, "error": "No image in clipboard."}

        app = RavenTUI()
        app.pending_permission = False
        app.chat_session = MagicMock()
        app.is_generating = False

        event = MagicMock()
        event.value = "/paste-image Explain screenshot"
        event.text_area = MagicMock()

        history_mock = MagicMock()
        app.query_one = MagicMock(return_value=history_mock)
        app.scroll_to_bottom = MagicMock()

        app.on_chat_input_submitted(event)

        # Should have mounted an error card
        history_mock.mount.assert_called()
        mounted_card = history_mock.mount.call_args[0][0]
        self.assertIn("Clipboard Error", mounted_card.raw_text)


if __name__ == "__main__":
    unittest.main()
