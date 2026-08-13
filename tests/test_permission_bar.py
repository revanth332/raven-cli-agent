"""
Unit and pilot tests for PermissionBar widget and input permission logic.
"""

import unittest
import asyncio
from agent.terminal_ui.permission_box import PermissionBar, PermissionBox
from agent.terminal_ui.app import RavenTUI


class TestPermissionBar(unittest.TestCase):

    def test_permission_bar_callbacks(self):
        allowed = False
        denied = False

        def on_allow():
            nonlocal allowed
            allowed = True

        def on_deny():
            nonlocal denied
            denied = True

        bar = PermissionBar("Action Required: execute_command", "Raven wants to execute dir.", on_allow, on_deny)
        self.assertEqual(bar.title_text, "Action Required: execute_command")
        self.assertEqual(bar.message_text, "Raven wants to execute dir.")

        bar.on_allow()
        self.assertTrue(allowed)

        bar.on_deny()
        self.assertTrue(denied)

        # Check backward compatibility alias
        self.assertEqual(PermissionBox, PermissionBar)

    def test_tui_permission_empty_enter_allows(self):
        app = RavenTUI()

        async def run_test():
            async with app.run_test() as pilot:
                app.ask_permission_ui("Action Required", "Execute command test")
                await pilot.pause()

                self.assertTrue(app.pending_permission)
                bar = app.query_one("#permission_bar", PermissionBar)
                self.assertIsNotNone(bar)

                # Submit empty text to allow
                chat_input = app.query_one("#chat_input")
                chat_input.text = ""
                await pilot.press("enter")
                await pilot.pause()

                self.assertFalse(app.pending_permission)
                self.assertTrue(app.permission_result)
                self.assertEqual(app.permission_instruction, "")

        asyncio.run(run_test())

    def test_tui_permission_text_enter_denies_with_instruction(self):
        app = RavenTUI()

        async def run_test():
            async with app.run_test() as pilot:
                app.ask_permission_ui("Action Required", "Execute command test")
                await pilot.pause()

                self.assertTrue(app.pending_permission)

                # Submit text instruction to deny with feedback
                chat_input = app.query_one("#chat_input")
                chat_input.text = "Don't run build, use lint"
                await pilot.press("enter")
                await pilot.pause()

                self.assertFalse(app.pending_permission)
                self.assertFalse(app.permission_result)
                self.assertEqual(app.permission_instruction, "Don't run build, use lint")

        asyncio.run(run_test())

    def test_unmount_unblocks_pending_permission(self):
        app = RavenTUI()

        async def run_test():
            async with app.run_test() as pilot:
                app.ask_permission_ui("Action Required", "Execute command test")
                await pilot.pause()

                self.assertTrue(app.pending_permission)
                self.assertFalse(app.permission_event.is_set())

                # Simulate app shutdown unmount
                app.on_unmount()
                await pilot.pause()

                self.assertTrue(app.permission_event.is_set())
                self.assertTrue(app.cancel_event.is_set())
                self.assertFalse(app.pending_permission)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

