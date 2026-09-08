"""
Unit tests for TUI initialization indicator and input disabling behavior (TUI-101).
"""

import unittest
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import OptionList, Static
from agent.terminal_ui.chat_input import ChatInput
from agent.terminal_ui.thinking_loader import ThinkingMessage


class MockTUIApp(App):
    def __init__(self):
        super().__init__()
        self.init_loader = None
        self.chat_session = None

    def compose(self) -> ComposeResult:
        with Vertical(id="bottom_bar"):
            yield Horizontal(id="thinking_container")
            yield ChatInput(id="chat_input")

    def set_input_ready(self, ready: bool, status_msg: str = "") -> None:
        try:
            chat_input = self.query_one("#chat_input", ChatInput)
            thinking_container = self.query_one("#thinking_container")
            if ready:
                chat_input.disabled = False
                chat_input.placeholder = "Ask Raven something... (Shift+Enter for newline, 'exit' to quit)"
                chat_input.focus()
                if getattr(self, "init_loader", None):
                    try:
                        self.init_loader.remove()
                    except Exception:
                        pass
                    self.init_loader = None
            else:
                chat_input.disabled = True
                chat_input.placeholder = status_msg or "Initializing AI session, please wait..."
                if not getattr(self, "init_loader", None) or self.init_loader.parent is None:
                    self.init_loader = ThinkingMessage(status_msg or "Initializing AI engine & loading session...")
                    try:
                        thinking_container.mount(self.init_loader)
                    except Exception:
                        pass
                elif self.init_loader:
                    self.init_loader.set_text(status_msg or "Initializing AI engine...")
        except Exception:
            pass


class TestUIInitialization(unittest.TestCase):

    def test_input_disabled_and_spinner_mounted_during_init(self):
        app = MockTUIApp()

        async def run_test():
            async with app.run_test() as pilot:
                # Trigger initializing state
                app.set_input_ready(False, "Initializing AI session, please wait...")
                await pilot.pause()

                chat_input = app.query_one("#chat_input", ChatInput)
                self.assertTrue(chat_input.disabled)
                self.assertEqual(chat_input.placeholder, "Initializing AI session, please wait...")

                # Verify ThinkingMessage is mounted in thinking_container
                thinking_container = app.query_one("#thinking_container", Horizontal)
                loader = thinking_container.query_one(ThinkingMessage)
                self.assertIsNotNone(loader)
                self.assertEqual(loader.FULL_TEXT, "Initializing AI session, please wait...")

                # Now trigger ready state
                app.set_input_ready(True)
                await pilot.pause()

                self.assertFalse(chat_input.disabled)
                self.assertIn("Ask Raven something...", chat_input.placeholder)

                # Verify ThinkingMessage was removed
                loaders = list(thinking_container.query(ThinkingMessage))
                self.assertEqual(len(loaders), 0)
                self.assertIsNone(app.init_loader)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
