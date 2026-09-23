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

    def test_timeline_creation_and_interleaving(self):
        from agent.terminal_ui.chat_message import (
            ResponseTimeline,
            TextBlock,
            ToolCallBlock,
            ToolResultBlock,
            StatusBlock,
            format_read_result,
        )

        timeline = ResponseTimeline()
        timeline.append_text("Inspecting project structure...")
        timeline.add_tool_call("read_file", "Read", "agent/main.py")
        timeline.add_tool_result("read_file", format_read_result("agent/main.py", "line 1\nline 2\nline 3\n"))
        timeline.append_text("Now modifying the setup...")
        timeline.add_status("Generation took 1.5s")

        self.assertEqual(len(timeline.blocks), 5)
        self.assertIsInstance(timeline.blocks[0], TextBlock)
        self.assertEqual(timeline.blocks[0].content, "Inspecting project structure...")
        self.assertIsInstance(timeline.blocks[1], ToolCallBlock)
        self.assertEqual(timeline.blocks[1].tool_name, "read_file")
        self.assertEqual(timeline.blocks[1].status, "completed")
        self.assertIsInstance(timeline.blocks[2], ToolResultBlock)
        self.assertIsInstance(timeline.blocks[3], TextBlock)
        self.assertEqual(timeline.blocks[3].content, "Now modifying the setup...")
        self.assertIsInstance(timeline.blocks[4], StatusBlock)

        plain = timeline.to_plain_text()
        self.assertIn("Inspecting project structure...", plain)
        self.assertIn("• Read(agent/main.py)", plain)
        self.assertIn("|_ Read 3 lines", plain)
        self.assertIn("Now modifying the setup...", plain)
        self.assertIn("Generation took 1.5s", plain)

    def test_timeline_streaming_incremental_append(self):
        from agent.terminal_ui.chat_message import ResponseTimeline, TextBlock

        timeline = ResponseTimeline()
        timeline.append_text("Let me ")
        timeline.append_text("check ")
        timeline.append_text("the code.")

        # Should coalesce into a single TextBlock
        self.assertEqual(len(timeline.blocks), 1)
        self.assertIsInstance(timeline.blocks[0], TextBlock)
        self.assertEqual(timeline.blocks[0].content, "Let me check the code.")

        # Add tool and then more text
        from rich.text import Text
        timeline.add_tool_call("execute_command", "Execute", "pytest")
        timeline.add_tool_result("execute_command", Text("   |_ Exit 0\n"))
        timeline.append_text("Everything passed successfully.")

        # Should now have 4 blocks
        self.assertEqual(len(timeline.blocks), 4)
        self.assertEqual(timeline.blocks[3].content, "Everything passed successfully.")

    def test_chat_message_widget_update_with_timeline(self):
        from agent.terminal_ui.chat_message import ResponseTimeline
        from rich.text import Text

        timeline = ResponseTimeline()
        timeline.append_text("Initial thought.")
        timeline.add_tool_call("read_file", "Read", "test.py")
        timeline.add_tool_result("read_file", Text("   |_ Read 10 lines (200 B)\n"))
        timeline.append_text("Concluding thought.")

        app = ChatMessageTestApp(role="assistant", raw_text="")

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#test_msg", ChatMessageWidget)
                widget.update_timeline(timeline)

                self.assertIn("Initial thought.", widget.raw_text)
                self.assertIn("• Read(test.py)", widget.raw_text)
                self.assertIn("Concluding thought.", widget.raw_text)

                btn = widget.query_one("#copy_btn", Static)
                await pilot.click("#copy_btn")
                await pilot.pause()
                self.assertEqual(str(btn.render()), "✓ Copied!")

        asyncio.run(run_test())

    def test_tool_result_formatters_command(self):
        from agent.terminal_ui.chat_message import format_command_result

        # Successful command
        raw_success = "Exit Code: 0\nSTDOUT:\n110 passed in 4.5s\n"
        res_succ = format_command_result("pytest", raw_success)
        self.assertIn("Exit 0", res_succ.plain)
        self.assertIn("110 passed in 4.5s", res_succ.plain)

        # Failed command
        raw_fail = "Exit Code: 1\nSTDERR:\nAssertionError: expected True but got False\n"
        res_fail = format_command_result("pytest", raw_fail)
        self.assertIn("Exit Code: 1 (Failed)", res_fail.plain)
        self.assertIn("AssertionError", res_fail.plain)

    def test_tool_result_formatters_read_and_find(self):
        from agent.terminal_ui.chat_message import format_read_result, format_find_result

        # Read formatting
        content = "line1\nline2\nline3\nline4\n"
        read_res = format_read_result("agent/app.py", content)
        self.assertIn("Read 4 lines", read_res.plain)

        # Find formatting
        find_res = format_find_result("main.py", "['agent/main.py']")
        self.assertIn("Found: agent/main.py", find_res.plain)

        not_found_res = format_find_result("foo.py", "File 'foo.py' not found.")
        self.assertIn("not found", not_found_res.plain)

    def test_tool_result_preview_dispatch(self):
        from agent.terminal_ui.chat_message import format_tool_result_preview

        # Patch file dispatch
        patch_res = format_tool_result_preview(
            "patch_file",
            {"file_path": "a.py", "search_block": "old", "replace_block": "new"},
            "Successfully updated 'a.py'."
        )
        self.assertIn("Updated a.py with 1 addition and 1 removal", patch_res.plain)

        # Execute command dispatch
        cmd_res = format_tool_result_preview(
            "execute_command",
            {"command": "git status"},
            "Exit Code: 0\nSTDOUT:\nworking tree clean\n"
        )
        self.assertIn("Exit 0", cmd_res.plain)
        self.assertIn("working tree clean", cmd_res.plain)

    def test_tool_result_expansion_toggle(self):
        from agent.terminal_ui.chat_message import ResponseTimeline, ToolResultWidget

        timeline = ResponseTimeline()
        timeline.append_text("Running suite...")
        long_output_1 = "Exit Code: 0\nSTDOUT:\n" + "\n".join([f"line_{i}" for i in range(12)])
        long_output_2 = "Exit Code: 0\nSTDOUT:\n" + "\n".join([f"extra_{i}" for i in range(10)])
        timeline.add_tool_call("execute_command", "Execute", "pytest")
        timeline.add_tool_result(
            "execute_command",
            tool_args={"command": "pytest"},
            raw_result=long_output_1,
            plain_text=long_output_1,
        )
        timeline.add_tool_call("execute_command", "Execute", "flake8")
        timeline.add_tool_result(
            "execute_command",
            tool_args={"command": "flake8"},
            raw_result=long_output_2,
            plain_text=long_output_2,
        )

        app = ChatMessageTestApp(role="assistant", raw_text="")

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#test_msg", ChatMessageWidget)
                widget.update_timeline(timeline)
                await pilot.pause()

                tool_widgets = list(widget.query(ToolResultWidget))
                self.assertEqual(len(tool_widgets), 2)
                self.assertFalse(tool_widgets[0].block.expanded)
                self.assertFalse(tool_widgets[1].block.expanded)

                # Click specifically on tool widget 0
                await pilot.click(tool_widgets[0])
                await pilot.pause()

                # Tool 0 must be expanded, but Tool 1 must remain collapsed
                self.assertTrue(tool_widgets[0].block.expanded)
                self.assertFalse(tool_widgets[1].block.expanded)

                # Click tool widget 1
                await pilot.click(tool_widgets[1])
                await pilot.pause()
                self.assertTrue(tool_widgets[0].block.expanded)
                self.assertTrue(tool_widgets[1].block.expanded)

                # Click tool widget 0 again to collapse
                await pilot.click(tool_widgets[0])
                await pilot.pause()
                self.assertFalse(tool_widgets[0].block.expanded)
                self.assertTrue(tool_widgets[1].block.expanded)

        asyncio.run(run_test())

    def test_assistant_message_direct_timeline_mount(self):
        from agent.terminal_ui.chat_message import ResponseTimeline, ToolResultWidget

        timeline = ResponseTimeline()
        timeline.append_text("Reloading previous turn...")
        timeline.add_tool_call("read_file", "Read", "agent/main.py")
        timeline.add_tool_result("read_file", tool_args={"file_path": "agent/main.py"}, raw_result="def main():\n    pass\n")

        class DirectTimelineApp(App):
            def compose(self) -> ComposeResult:
                yield ChatMessageWidget(role="assistant", timeline=timeline, id="reloaded_card")

        app = DirectTimelineApp()

        async def run_test():
            async with app.run_test() as pilot:
                widget = app.query_one("#reloaded_card", ChatMessageWidget)
                await pilot.pause()

                # Verify timeline container has children rendered on mount without user clicking
                tool_widgets = list(widget.query(ToolResultWidget))
                self.assertEqual(len(tool_widgets), 1)
                self.assertIn("• Read(agent/main.py)", widget.raw_text)
                self.assertIn("Read 2 lines", widget.raw_text)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
