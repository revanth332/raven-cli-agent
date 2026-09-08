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

    def test_update_before_mount_with_rich_text(self):
        from rich.text import Text

        styled_text = Text()
        styled_text.append("• ", style="bold cyan")
        styled_text.append("Read", style="bold cyan")
        styled_text.append("(/path/to/file)", style="dim white")

        widget = ChatMessageWidget(role="assistant", raw_text="")
        # Call update before widget is mounted or composed
        widget.update(styled_text)

        class PreMountApp(App):
            def compose(self) -> ComposeResult:
                yield widget

        app = PreMountApp()

        async def run_test():
            async with app.run_test() as pilot:
                await pilot.pause()
                content_static = widget.query_one("#msg_content", Static)
                rendered_str = str(content_static.render())
                self.assertIn("• Read(/path/to/file)", rendered_str)
                self.assertNotIn("[bold cyan]", rendered_str)
                self.assertNotIn("[bold cyan]", widget.raw_text)
                self.assertEqual(widget.raw_text, "• Read(/path/to/file)")

        asyncio.run(run_test())

    def test_update_with_group_combines_tool_logs_and_raw_text(self):
        from rich.text import Text
        from rich.markdown import Markdown
        from rich.console import Group

        tool_logs = Text("• Read(test.py)")
        response_text = "Here is the summary."
        group = Group(tool_logs, Markdown(response_text))

        app = ChatMessageTestApp(role="assistant", raw_text="")

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#test_msg", ChatMessageWidget)
                widget.update(group, raw_text=response_text)
                self.assertEqual(widget.raw_text, "• Read(test.py)\n\nHere is the summary.")

        asyncio.run(run_test())

    def test_update_with_group_tool_logs_only(self):
        from rich.text import Text
        from rich.console import Group

        tool_logs = Text("• Update(main.py)")
        group = Group(tool_logs)

        app = ChatMessageTestApp(role="assistant", raw_text="")

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#test_msg", ChatMessageWidget)
                widget.update(group)
                self.assertEqual(widget.raw_text, "• Update(main.py)")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
