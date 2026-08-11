"""
Async pilot test for TUI session switching and modal interaction.
"""

import unittest
import asyncio
from textual.app import App, ComposeResult
from agent.terminal_ui.session_select_modal import SessionSelectModal
from agent.core import session_manager


class SessionTestApp(App):
    def compose(self) -> ComposeResult:
        yield SessionSelectModal()


class TestUISessions(unittest.TestCase):

    def test_session_select_modal_render(self):
        s1 = session_manager.create_session(title="Modal Test Session 1")
        s2 = session_manager.create_session(title="Modal Test Session 2")

        app = SessionTestApp()

        async def run_modal_test():
            async with app.run_test() as pilot:
                modal = app.query_one(SessionSelectModal)
                self.assertIsNotNone(modal)
                opt_list = modal.query_one("#session_option_list")
                self.assertGreaterEqual(opt_list.option_count, 1)

        asyncio.run(run_modal_test())


if __name__ == "__main__":
    unittest.main()
