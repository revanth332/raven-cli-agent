"""
Unit tests for ChatMessageWidget.
"""

import unittest
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Static
from agent.terminal_ui.chat_message import ChatMessageWidget


class ChatMessageTestApp(App):
    def __init__(self, role: str = "user", raw_text: str = ""):
        super().__init__()
        self.msg_role = role
        self.msg_text = raw_text

    def compose(self) -> ComposeResult:
        yield ChatMessageWidget(role=self.msg_role, raw_text=self.msg_text, id="test_msg")


class TestChatMessageWidget(unittest.TestCase):

    def test_user_message_initialization_and_copy(self):
        app = ChatMessageTestApp(role="user", raw_text="How do I use Raven CLI?")

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#test_msg", ChatMessageWidget)
                self.assertEqual(widget.role, "user")
                self.assertEqual(widget.raw_text, "How do I use Raven CLI?")

                btn = widget.query_one("#copy_btn", Static)
                self.assertEqual(str(btn.render()), "Copy")

                await pilot.click("#copy_btn")
                await pilot.pause()

                self.assertEqual(str(btn.render()), "✓ Copied!")

        asyncio.run(run_test())

    def test_assistant_message_update_and_copy(self):
        app = ChatMessageTestApp(role="assistant", raw_text="")

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#test_msg", ChatMessageWidget)
                self.assertEqual(widget.role, "assistant")

                # Update message with content
                new_text = "Here is the architectural guidance..."
                widget.update(new_text)
                self.assertEqual(widget.raw_text, new_text)

                btn = widget.query_one("#copy_btn", Static)
                await pilot.click("#copy_btn")
                await pilot.pause()

                self.assertEqual(str(btn.render()), "✓ Copied!")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
