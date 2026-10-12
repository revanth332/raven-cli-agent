"""
Modal screen for selecting, switching, or deleting chat sessions in Textual TUI.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import OptionList, Input, Static, Button
from textual.widgets.option_list import Option
from rich.table import Table

from agent.core.session_manager import list_sessions, delete_session, get_active_session_id


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

    CSS_PATH = "styles/session_select_modal.tcss"

    def __init__(self, active_session_id: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_session_id = active_session_id or get_active_session_id()
        self.all_sessions: List[Dict[str, Any]] = []
        self._current_filtered_sessions: List[Dict[str, Any]] = []
        self._last_highlighted_index: Optional[int] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="session_modal_container"):
            with Horizontal(id="session_header_row"):
                with Horizontal(id="session_header_left"):
                    yield Static("SELECT CHAT SESSION", id="session_modal_title")
                    yield Static("[0 Sessions Active]", id="session_count_badge")
                yield Static(
                    "[bold #00E5BF][?][/bold #00E5BF] [dim #94A3B8]Help[/dim #94A3B8]  "
                    "[dim #475569]|[/dim #475569]  "
                    "[bold #00E5BF][Esc][/bold #00E5BF] [dim #94A3B8]Close[/dim #94A3B8]",
                    id="session_help_btn"
                )

            with Horizontal(id="session_search_bar"):
                yield Static(">", id="session_search_icon")
                yield Input(
                    placeholder="Search sessions by title, id, or agent...",
                    id="session_search_input"
                )
                yield Static(
                    "[dim](↑/↓ to navigate,[/dim] [bold #00E5BF][↑/↓][/bold #00E5BF] [dim]Navigate[/dim]  "
                    "[bold #00E5BF][Enter][/bold #00E5BF] [dim]Resume[/dim]  "
                    "[bold #00E5BF][Del][/bold #00E5BF] [dim]Delete[/dim][dim])[/dim]",
                    id="session_search_shortcuts"
                )

            yield OptionList(id="session_option_list")

            with Horizontal(id="session_modal_actions"):
                with Horizontal(id="session_actions_left"):
                    yield Button("Resume Session [Enter]", id="btn_resume")
                    yield Button("Delete [Del]", id="btn_delete")
                with Horizontal(id="session_actions_right"):
                    yield Button("New Session [^N]", id="btn_new")
                    yield Button("Cancel [Esc]", id="btn_cancel")

    def on_mount(self) -> None:
        self.all_sessions = list_sessions()
        self.populate_options(self.all_sessions)
        self.query_one("#session_search_input", Input).focus()

    def _build_option_grid(self, sess: Dict[str, Any], is_highlighted: bool = False, is_active: bool = False) -> Table:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=3, no_wrap=True)
        grid.add_column(justify="right", no_wrap=True)

        title = sess.get("title", "Untitled") or "Untitled"
        parent_id = sess.get("parent_session_id")
        fork_badge = " [#A3E635][Fork][/#A3E635]" if parent_id else ""
        active_badge = " [bold #10B981][ACTIVE][/bold #10B981]" if is_active else ""

        left_line1 = f"[bold #00E5BF]{title}[/bold #00E5BF]{active_badge}{fork_badge}"

        rel_time = format_relative_time(sess.get("updated_at") or sess.get("created_at") or "")
        if is_highlighted:
            right_line1 = f"[dim #94A3B8]{rel_time}[/dim #94A3B8]  [bold #00E5BF][Enter] Select[/bold #00E5BF]"
        else:
            right_line1 = f"[dim #94A3B8]{rel_time}[/dim #94A3B8]" if rel_time else ""

        grid.add_row(left_line1, right_line1)

        p_name = sess.get("project_name") or "raven-cli-agent"
        sid = sess.get("session_id", "unknown")
        sid_short = sid[:8]
        turns_str = format_turn_count(sess.get("turn_count", 0))
        tokens_str = format_token_count(sess.get("total_tokens", 0))

        left_line2 = (
            f"[#38BDF8]{p_name}[/#38BDF8] [dim #64748B]•[/dim #64748B] "
            f"[dim #94A3B8]{sid_short}[/dim #94A3B8] [dim #64748B]•[/dim #64748B] "
            f"[dim #94A3B8]{turns_str}[/dim #94A3B8] [dim #64748B]•[/dim #64748B] "
            f"[dim #94A3B8]{tokens_str}[/dim #94A3B8]"
        )
        grid.add_row(left_line2, "")
        return grid

    def populate_options(self, sessions: List[Dict[str, Any]], target_highlight: int = 0) -> None:
        self._current_filtered_sessions = sessions
        opt_list = self.query_one("#session_option_list", OptionList)
        opt_list.clear_options()

        # Update counter badge
        badge = self.query_one("#session_count_badge", Static)
        if len(sessions) == len(self.all_sessions):
            badge.update(f"[{len(self.all_sessions)} Sessions Active]")
        else:
            badge.update(f"[{len(sessions)}/{len(self.all_sessions)} Sessions Active]")

        if not sessions:
            opt_list.add_option(Option("[#94A3B8]No chat sessions found[/#94A3B8]", id="none"))
            self._last_highlighted_index = None
            return

        safe_index = max(0, min(target_highlight, len(sessions) - 1))
        self._last_highlighted_index = safe_index

        for idx, sess in enumerate(sessions):
            sid = sess.get("session_id", "unknown")
            is_active = (sid == self.active_session_id)
            is_highlight = (idx == safe_index)
            grid = self._build_option_grid(sess, is_highlighted=is_highlight, is_active=is_active)
            opt_list.add_option(Option(grid, id=sid))

        opt_list.highlighted = safe_index

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        new_idx = getattr(event, "option_index", None)
        if new_idx is None or not self._current_filtered_sessions:
            return

        opt_list = self.query_one("#session_option_list", OptionList)
        if self._last_highlighted_index is not None and self._last_highlighted_index != new_idx:
            if 0 <= self._last_highlighted_index < len(self._current_filtered_sessions):
                old_sess = self._current_filtered_sessions[self._last_highlighted_index]
                old_grid = self._build_option_grid(
                    old_sess,
                    is_highlighted=False,
                    is_active=(old_sess.get("session_id") == self.active_session_id)
                )
                try:
                    opt_list.replace_option_prompt_at_index(self._last_highlighted_index, old_grid)
                except Exception:
                    pass

        if 0 <= new_idx < len(self._current_filtered_sessions):
            new_sess = self._current_filtered_sessions[new_idx]
            new_grid = self._build_option_grid(
                new_sess,
                is_highlighted=True,
                is_active=(new_sess.get("session_id") == self.active_session_id)
            )
            try:
                opt_list.replace_option_prompt_at_index(new_idx, new_grid)
            except Exception:
                pass

        self._last_highlighted_index = new_idx

    def on_input_changed(self, event: Input.Changed) -> None:
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
            self.dismiss(None)
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
        elif event.key == "enter":
            btn_delete = self.query_one("#btn_delete", Button)
            btn_cancel = self.query_one("#btn_cancel", Button)
            btn_new = self.query_one("#btn_new", Button)
            if not btn_cancel.has_focus and not btn_delete.has_focus and not btn_new.has_focus:
                self.resume_highlighted_session()
                event.prevent_default()
                event.stop()
        elif event.key in ["question_mark", "?"]:
            search_input = self.query_one("#session_search_input", Input)
            if not search_input.has_focus:
                self.show_help()
                event.prevent_default()
                event.stop()

    def resume_highlighted_session(self) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is not None and opt_list.option_count > 0:
            opt = opt_list.get_option_at_index(opt_list.highlighted)
            if opt and opt.id and opt.id != "none":
                self.dismiss(str(opt.id))

    def delete_highlighted_session(self) -> None:
        opt_list = self.query_one("#session_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return

        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.id == "none":
            return

        current_idx = opt_list.highlighted
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
                self.populate_options(filtered, target_highlight=current_idx)
            else:
                self.populate_options(self.all_sessions, target_highlight=current_idx)

        # Restore focus back to search input so arrow navigation and search continue seamlessly
        self.query_one("#session_search_input", Input).focus()

    def show_help(self) -> None:
        self.notify(
            "Shortcuts:\n"
            "• ↑ / ↓: Navigate sessions\n"
            "• Enter: Resume selected session\n"
            "• Del / Ctrl+D: Delete session\n"
            "• Ctrl+N: Start fresh session\n"
            "• Esc: Close modal",
            title="Sessions Help",
            severity="information"
        )

    def on_click(self, event: events.Click) -> None:
        if event.widget and event.widget.id == "session_help_btn":
            self.show_help()
        elif event.widget and event.widget.id in ("session_search_bar", "session_search_icon"):
            self.query_one("#session_search_input", Input).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id and event.option.id != "none":
            self.dismiss(str(event.option.id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_resume":
            self.resume_highlighted_session()
        elif event.button.id == "btn_delete":
            self.delete_highlighted_session()
        elif event.button.id == "btn_new":
            self.dismiss("__new__")




