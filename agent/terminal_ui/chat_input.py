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

    def on_key(self, event: events.Key) -> None:
        if event.key in ("shift+enter", "shift+return", "alt+enter", "ctrl+j", "ctrl+enter") or (
            event.key in ("enter", "return") and ("shift" in event.modifiers or "alt" in event.modifiers or "ctrl" in event.modifiers)
        ):
            self.insert("\n")
            event.prevent_default()
            event.stop()
            return

        if event.key in ("enter", "return") and self.text.endswith("\\"):
            self.text = self.text[:-1]
            self.insert("\n")
            event.prevent_default()
            event.stop()
            return

        # Arrow navigation for in-stream decision cards when input is empty
        if getattr(self.app, "pending_questionnaire", False) and not self.text.strip():
            if event.key in ("left", "up"):
                try:
                    bar = self.app.query_one("#questionnaire_bar")
                    if hasattr(bar, "select_previous"):
                        bar.select_previous()
                        event.prevent_default()
                        event.stop()
                        return
                except Exception:
                    pass
            elif event.key in ("right", "down"):
                try:
                    bar = self.app.query_one("#questionnaire_bar")
                    if hasattr(bar, "select_next"):
                        bar.select_next()
                        event.prevent_default()
                        event.stop()
                        return
                except Exception:
                    pass

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