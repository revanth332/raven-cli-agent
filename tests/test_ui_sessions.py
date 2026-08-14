"""
Async pilot test for TUI session switching and modal interaction.
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from textual.app import App, ComposeResult
from agent.terminal_ui.session_select_modal import SessionSelectModal
from agent.core import session_manager


class SessionTestApp(App):
    def compose(self) -> ComposeResult:
        yield SessionSelectModal()


class TestUISessions(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.orig_get_dir = session_manager.get_sessions_dir
        session_manager.get_sessions_dir = lambda: self.tmp_dir

    def tearDown(self):
        session_manager.get_sessions_dir = self.orig_get_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_session_select_modal_render_and_delete(self):
        s1 = session_manager.create_session(title="Modal Test Session 1")
        s1["messages"].append({"role": "user", "content": "hello"})
        session_manager.save_session(s1)

        s2 = session_manager.create_session(title="Modal Test Session 2")
        s2["messages"].append({"role": "user", "content": "hi"})
        session_manager.save_session(s2)

        app = SessionTestApp()

        async def run_modal_test():
            async with app.run_test() as pilot:
                modal = app.query_one(SessionSelectModal)
                self.assertIsNotNone(modal)
                opt_list = modal.query_one("#session_option_list")
                self.assertEqual(opt_list.option_count, 2)

                # Test navigation
                self.assertEqual(opt_list.highlighted, 0)

                await pilot.press("down")
                self.assertEqual(opt_list.highlighted, 1)

                await pilot.press("up")
                self.assertEqual(opt_list.highlighted, 0)

                # Test delete highlighted session
                modal.delete_highlighted_session()
                self.assertEqual(opt_list.option_count, 1)

        asyncio.run(run_modal_test())


if __name__ == "__main__":
    unittest.main()
