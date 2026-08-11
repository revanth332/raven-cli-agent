"""
Modal screen for selecting, switching, or deleting chat sessions in Textual TUI.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import OptionList, Input, Static, Button
from textual.widgets.option_list import Option

from agent.core.session_manager import list_sessions, delete_session


class SessionSelectModal(ModalScreen[str]):
    """
    Interactive modal popup displaying all stored chat sessions with auto-search filtering.
    Returns selected session_id or None if dismissed.
    """

    DEFAULT_CSS = """
    SessionSelectModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    #session_modal_container {
        width: 70%;
        max-width: 80;
        height: 65%;
        background: #1e1e1e;
        border: solid #06B6D4;
        padding: 1 2;
    }

    #session_modal_title {
        text-align: center;
        margin-bottom: 1;
        color: #06B6D4;
        text-style: bold;
    }

    #session_search_input {
        margin-bottom: 1;
        background: #252526;
        border: solid #06B6D4;
    }

    #session_option_list {
        height: 1fr;
        background: #1e1e1e;
        border: none;
        margin-bottom: 1;
    }

    #session_modal_actions {
        height: auto;
        align: right middle;
    }

    .modal-btn {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="session_modal_container"):
            yield Static("💬 SELECT CHAT SESSION", id="session_modal_title")
            yield Input(placeholder="Search sessions by title or ID...", id="session_search_input")
            yield OptionList(id="session_option_list")
            with Horizontal(id="session_modal_actions"):
                yield Button("Cancel", id="btn_cancel", classes="modal-btn")

    def on_mount(self):
        self.all_sessions = list_sessions()
        self.populate_options(self.all_sessions)
        self.query_one("#session_search_input", Input).focus()

    def populate_options(self, sessions):
        opt_list = self.query_one("#session_option_list", OptionList)
        opt_list.clear_options()

        if not sessions:
            opt_list.add_option(Option("[dim]No sessions found[/dim]", id="none"))
            return

        for sess in sessions:
            sid = sess.get("session_id", "unknown")
            title = sess.get("title", "Untitled")
            model = sess.get("model_name", "gpt-4o")
            msgs = sess.get("message_count", 0)
            updated = sess.get("updated_at", "")[:10]

            label = f"[bold cyan]{title}[/bold cyan] [dim]({sid})[/dim]\n  [dim white]Model: {model} │ Messages: {msgs} │ Updated: {updated}[/dim white]"
            opt_list.add_option(Option(label, id=sid))

    def on_input_changed(self, event: Input.Changed):
        query = event.value.strip().lower()
        if not query:
            self.populate_options(self.all_sessions)
            return

        filtered = [
            s for s in self.all_sessions
            if query in s.get("title", "").lower() or query in s.get("session_id", "").lower()
        ]
        self.populate_options(filtered)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option.id and event.option.id != "none":
            self.dismiss(str(event.option.id))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(None)
