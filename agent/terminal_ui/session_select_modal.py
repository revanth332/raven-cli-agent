"""
Modal screen for selecting, switching, or deleting chat sessions in Textual TUI.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import OptionList, Input, Static, Button
from textual.widgets.option_list import Option
from rich.table import Table

from agent.core.session_manager import (
    list_sessions,
    delete_session,
    rename_session,
    toggle_pin_session,
    get_active_session_id
)


def format_relative_time(iso_str: str) -> str:
    """Returns human-readable relative time string (e.g. '2m ago', '42m ago', '3h ago', 'Yesterday', '2d ago')."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = max(0, int(diff.total_seconds()))

        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days == 1:
            return "Yesterday"
        if days < 7:
            return f"{days}d ago"
        if days < 30:
            weeks = days // 7
            return f"{weeks}w ago" if weeks > 1 else f"{days}d ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        years = days // 365
        return f"{years}y ago"
    except Exception:
        return ""


def format_token_count(tokens: Optional[int]) -> str:
    """Formats token count into human-friendly string (e.g. '52.4k tokens', '9.4k tokens', '800 tokens')."""
    if tokens is None or tokens <= 0:
        return "0 tokens"
    if tokens < 1000:
        return f"{tokens} tokens"
    k_val = tokens / 1000.0
    return f"{k_val:.1f}k tokens"


def format_turn_count(turns: Optional[int]) -> str:
    """Formats turn count into human-friendly string (e.g. '18 turns', '1 turn')."""
    if turns == 1:
        return "1 turn"
    return f"{turns or 0} turns"


class SessionSelectModal(ModalScreen[str]):
    """
    Interactive modal popup displaying stored chat sessions with real-time search,
    rich metadata (turns, tokens, relative times), and keyboard shortcuts.
    Returns selected session_id, '__new__', or None if dismissed.
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", priority=True),
    ]
    CSS_PATH = "styles/session_select_modal.tcss"

    def __init__(self, active_session_id: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_session_id = active_session_id or get_active_session_id()
        self.all_sessions: List[Dict[str, Any]] = []
        self._current_filtered_sessions: List[Dict[str, Any]] = []
        self._renaming_sid: Optional[str] = None

    def action_dismiss_modal(self) -> None:
        if self._renaming_sid is not None:
            self._renaming_sid = None
            inp = self.query_one("#session_search_input", Input)
            inp.placeholder = "Search"
            inp.value = ""
            self.populate_options(self.all_sessions)
        else:
            self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="session_modal_container"):
            with Horizontal(id="session_header_row"):
                yield Static("Sessions", id="session_modal_title")
                yield Static("esc", id="session_close_hint")

            yield Input(
                placeholder="Search",
                id="session_search_input"
            )

            yield OptionList(id="session_option_list")

            yield Static(
                "pin/unpin [dim #71717a]ctrl+f[/dim #71717a]    "
                "delete [dim #71717a]ctrl+d[/dim #71717a]    "
                "rename [dim #71717a]ctrl+r[/dim #71717a]",
                id="session_footer_shortcuts"
            )

    def on_mount(self) -> None:
        self.all_sessions = list_sessions()
        self.populate_options(self.all_sessions)
        self.query_one("#session_search_input", Input).focus()

    def _format_date_header(self, iso_str: str) -> str:
        """Formats ISO date string into day header (e.g. 'Fri Sep 25 2026')."""
        if not iso_str:
            return datetime.now().strftime("%a %b %d %Y")
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%a %b %d %Y")
        except Exception:
            return datetime.now().strftime("%a %b %d %Y")

    def populate_options(self, sessions: List[Dict[str, Any]], target_sid: Optional[str] = None) -> None:
        self._current_filtered_sessions = sessions
        opt_list = self.query_one("#session_option_list", OptionList)
        opt_list.clear_options()

        if not sessions:
            opt_list.add_option(Option("[dim #71717a]No chat sessions found[/dim #71717a]", disabled=True, id="none"))
            return

        last_date = None
        target_highlight_idx = None
        first_valid_idx = None

        for idx, sess in enumerate(sessions):
            raw_date = sess.get("updated_at") or sess.get("created_at") or ""
            date_header = self._format_date_header(raw_date)
            if date_header != last_date:
                opt_list.add_option(Option(f"[bold #10B981]{date_header}[/bold #10B981]", disabled=True))
                last_date = date_header

            sid = sess.get("session_id", "unknown")
            title = sess.get("title", "Untitled") or "Untitled"
            is_pinned = sess.get("pinned", False)
            prefix = "📌 " if is_pinned else ""

            current_option_idx = opt_list.option_count
            opt_list.add_option(Option(f"{prefix}{title}", id=sid))

            if first_valid_idx is None:
                first_valid_idx = current_option_idx

            if target_sid and sid == target_sid:
                target_highlight_idx = current_option_idx

        # Set highlight
        if target_highlight_idx is not None:
            opt_list.highlighted = target_highlight_idx
        elif first_valid_idx is not None:
            opt_list.highlighted = first_valid_idx

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._renaming_sid is not None:
            return
        query = event.value.strip().lower()
        if not query:
            self.populate_options(self.all_sessions)
            return

        filtered = [
            s for s in self.all_sessions
            if query in s.get("title", "").lower()
            or query in s.get("session_id", "").lower()
            or query in s.get("project_name", "").lower()
        ]
        self.populate_options(filtered)

    def on_key(self, event: events.Key) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)

        if event.key == "down":
            opt_list.action_cursor_down()
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            opt_list.action_cursor_up()
            event.prevent_default()
            event.stop()
        elif event.key in ["page_down", "pagedown"]:
            opt_list.action_page_down()
            event.prevent_default()
            event.stop()
        elif event.key in ["page_up", "pageup"]:
            opt_list.action_page_up()
            event.prevent_default()
            event.stop()
        elif event.key == "escape":
            self.action_dismiss_modal()
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+n":
            self.dismiss("__new__")
            event.prevent_default()
            event.stop()
        elif event.key in ["delete", "ctrl+d"]:
            self.delete_highlighted_session()
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+f":
            self.toggle_highlighted_pin()
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+r":
            self.start_rename_highlighted()
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            if self._renaming_sid is not None:
                inp = self.query_one("#session_search_input", Input)
                new_title = inp.value.strip()
                if new_title:
                    rename_session(self._renaming_sid, new_title)
                    self.all_sessions = list_sessions()
                    if self.app:
                        chat_sess = getattr(self.app, "chat_session", None)
                        if chat_sess and getattr(chat_sess, "session_id", None) == self._renaming_sid:
                            chat_sess.session_title = new_title
                        if hasattr(self.app, "update_status_bar"):
                            try:
                                self.app.update_status_bar()
                            except Exception:
                                pass
                target = self._renaming_sid
                self._renaming_sid = None
                inp.placeholder = "Search"
                inp.value = ""
                self.populate_options(self.all_sessions, target_sid=target)
            else:
                self.resume_highlighted_session()
            event.prevent_default()
            event.stop()

    def start_rename_highlighted(self) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return
        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.disabled or opt.id == "none":
            return

        self._renaming_sid = str(opt.id)
        current_title = ""
        for s in self.all_sessions:
            if s.get("session_id") == self._renaming_sid:
                current_title = s.get("title", "")
                break

        inp = self.query_one("#session_search_input", Input)
        inp.placeholder = "Enter new session title and press Enter..."
        inp.value = current_title
        inp.focus()

    def toggle_highlighted_pin(self) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return
        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.disabled or opt.id == "none":
            return

        sid = str(opt.id)
        toggle_pin_session(sid)
        self.all_sessions = list_sessions()
        inp = self.query_one("#session_search_input", Input)
        query = inp.value.strip().lower()
        if query and self._renaming_sid is None:
            filtered = [
                s for s in self.all_sessions
                if query in s.get("title", "").lower()
                or query in s.get("session_id", "").lower()
                or query in s.get("project_name", "").lower()
            ]
            self.populate_options(filtered, target_sid=sid)
        else:
            self.populate_options(self.all_sessions, target_sid=sid)

    def resume_highlighted_session(self) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is not None and opt_list.option_count > 0:
            opt = opt_list.get_option_at_index(opt_list.highlighted)
            if opt and opt.id and not opt.disabled and opt.id != "none":
                self.dismiss(str(opt.id))

    def delete_highlighted_session(self) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return

        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.disabled or opt.id == "none":
            return

        session_id = str(opt.id)
        if delete_session(session_id):
            self.all_sessions = list_sessions()
            search_input = self.query_one("#session_search_input", Input)
            query = search_input.value.strip().lower()
            if query and self._renaming_sid is None:
                filtered = [
                    s for s in self.all_sessions
                    if query in s.get("title", "").lower()
                    or query in s.get("session_id", "").lower()
                    or query in s.get("project_name", "").lower()
                ]
                self.populate_options(filtered)
            else:
                self.populate_options(self.all_sessions)

        self.query_one("#session_search_input", Input).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id and not event.option.disabled and event.option.id != "none":
            self.dismiss(str(event.option.id))




