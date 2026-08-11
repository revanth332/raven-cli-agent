from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea
from textual import events


class ChatInput(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("shift+enter", "newline", "Newline", priority=True),
        Binding("shift+return", "newline", "Newline", priority=True),
        Binding("alt+enter", "newline", "Newline", priority=True),
        Binding("ctrl+j", "newline", "Newline", priority=True),
    ]

    class Submitted(Message):
        def __init__(self, text_area: "ChatInput", value: str) -> None:
            self.text_area = text_area
            self.value = value
            super().__init__()

    def _on_key(self, event: events.Key) -> None:
        if event.key in ("shift+enter", "shift+return", "alt+enter", "ctrl+j") or (
            event.key in ("enter", "return") and ("shift" in event.modifiers or "alt" in event.modifiers)
        ):
            self.insert("\n")
            event.prevent_default()
            event.stop()
            return
        super()._on_key(event)

    def action_submit(self) -> None:
        try:
            autocomplete = self.app.query_one("#autocomplete_list")
            if autocomplete.styles.display == "block":
                if hasattr(self.app, "select_autocomplete_option"):
                    self.app.select_autocomplete_option()
                return
        except Exception:
            pass
        self.post_message(self.Submitted(self, self.text))

    def action_newline(self) -> None:
        self.insert("\n")