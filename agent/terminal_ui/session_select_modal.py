"""
Modal screen for selecting, switching, or deleting chat sessions in Textual TUI.
"""

from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import OptionList, Input, Static, Button
from textual.widgets.option_list import Option
from rich.text import Text

from agent.core.session_manager import list_sessions, delete_session


class SessionSelectModal(ModalScreen[str]):
    """
    Interactive modal popup displaying all stored chat sessions with auto-search filtering.
    Returns selected session_id or None if dismissed.
    """

    CSS_PATH = "styles/session_select_modal.tcss"

    def compose(self) -> ComposeResult:
        with Vertical(id="session_modal_container"):
            yield Static("💬 SELECT CHAT SESSION", id="session_modal_title")
            yield Input(placeholder="Search sessions... (↑/↓ to navigate, Del to delete)", id="session_search_input")
            yield OptionList(id="session_option_list")
            with Horizontal(id="session_modal_actions"):
                yield Button("Delete", id="btn_delete")
                yield Button("Cancel", id="btn_cancel")

    def on_mount(self):
        self.all_sessions = list_sessions()
        self.populate_options(self.all_sessions)
        self.query_one("#session_search_input", Input).focus()

    def populate_options(self, sessions):
        opt_list = self.query_one("#session_option_list", OptionList)
        opt_list.clear_options()

        if not sessions:
            opt_list.add_option(Option("[#94A3B8]No sessions found[/#94A3B8]", id="none"))
            return

        for sess in sessions:
            sid = sess.get("session_id", "unknown")
            title = sess.get("title", "Untitled")
            msgs = sess.get("message_count", 0)
            project_name = sess.get("project_name", "")

            if project_name:
                label = f"[bold cyan]{title}[/bold cyan] - [dim white]{project_name}[/dim white] [dim]({sid})[/dim]\n │ Messages: {msgs}"
            else:
                label = f"[bold cyan]{title}[/bold cyan] [dim]({sid})[/dim]\n │ Messages: {msgs}"
            opt_list.add_option(Option(label, id=sid))

        if sessions:
            opt_list.highlighted = 0

    def on_input_changed(self, event: Input.Changed):
        query = event.value.strip().lower()
        if not query:
            self.populate_options(self.all_sessions)
            return

        filtered = [
            s for s in self.all_sessions
            if query in s.get("title", "").lower() or query in s.get("session_id", "").lower() or query in s.get("project_name", "").lower()
        ]
        self.populate_options(filtered)

    def on_key(self, event: events.Key) -> None:
        search_input = self.query_one("#session_search_input", Input)
        opt_list = self.query_one("#session_option_list", OptionList)

        if search_input.has_focus or opt_list.has_focus:
            if event.key == "down":
                opt_list.action_cursor_down()
                event.prevent_default()
                event.stop()
            elif event.key == "up":
                opt_list.action_cursor_up()
                event.prevent_default()
                event.stop()
            elif event.key == "enter":
                if opt_list.highlighted is not None and opt_list.option_count > 0:
                    opt = opt_list.get_option_at_index(opt_list.highlighted)
                    if opt and opt.id and opt.id != "none":
                        self.dismiss(str(opt.id))
                        event.prevent_default()
                        event.stop()
            elif event.key in ["delete", "ctrl+d"]:
                self.delete_highlighted_session()
                event.prevent_default()
                event.stop()

    def delete_highlighted_session(self):
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return

        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.id == "none":
            return

        session_id = str(opt.id)
        if delete_session(session_id):
            self.all_sessions = list_sessions()
            search_input = self.query_one("#session_search_input", Input)
            query = search_input.value.strip().lower()
            if query:
                filtered = [
                    s for s in self.all_sessions
                    if query in s.get("title", "").lower()
                    or query in s.get("session_id", "").lower()
                    or query in s.get("project_name", "").lower()
                ]
                self.populate_options(filtered)
            else:
                self.populate_options(self.all_sessions)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option.id and event.option.id != "none":
            self.dismiss(str(event.option.id))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_delete":
            self.delete_highlighted_session()




