from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea
class ChatInput(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("shift+enter", "newline", "Newline", priority=True),
    ]

    class Submitted(Message):
        def __init__(self, text_area: "ChatInput", value: str) -> None:
            self.text_area = text_area
            self.value = value
            super().__init__()

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