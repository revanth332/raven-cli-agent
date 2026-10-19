"""
Modal screen for viewing discovered subagents in Textual TUI.
"""

from typing import Any, Dict, List
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import OptionList, Input, Static
from textual.widgets.option_list import Option

from agent.core.subagent_manager import discover_subagents


class SubagentsModal(ModalScreen[str | None]):
    """
    Modal screen listing all discovered subagents (built-in + global + project).
    Provides debounced search and clean viewer layout.
    """

    CSS_PATH = "styles/subagents_modal.tcss"

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.all_subagents: List[Dict[str, Any]] = []
        self.filtered_subagents: List[Dict[str, Any]] = []
        self._search_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="subagents_modal_container"):
            with Horizontal(id="subagents_header_row"):
                yield Static("Subagents", id="subagents_modal_title")
                yield Static("esc", id="subagents_close_hint")
            yield Input(
                placeholder="Search subagents...",
                id="subagents_search_input",
            )
            yield OptionList(id="subagents_option_list")

    def on_mount(self) -> None:
        self.refresh_subagents()
        self.query_one("#subagents_search_input", Input).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def refresh_subagents(self) -> None:
        self.all_subagents = discover_subagents()
        search_val = self.query_one("#subagents_search_input", Input).value.strip().lower()
        self.filter_and_populate(search_val)

    def filter_and_populate(self, query: str = "") -> None:
        if not query:
            self.filtered_subagents = list(self.all_subagents)
        else:
            self.filtered_subagents = [
                s
                for s in self.all_subagents
                if query in s.get("name", "").lower()
                or query in s.get("description", "").lower()
                or query in s.get("scope", "").lower()
            ]
        self.populate_options(self.filtered_subagents)

    def populate_options(self, subagents: List[Dict[str, Any]]) -> None:
        opt_list = self.query_one("#subagents_option_list", OptionList)
        prev_highlighted = opt_list.highlighted
        opt_list.clear_options()

        if not subagents:
            opt_list.add_option(
                Option("[dim #71717a]No matching subagents found[/dim #71717a]", id="none", disabled=True)
            )
            return

        opt_list.add_option(
            Option("[bold #10B981]Subagents[/bold #10B981]", id="header_subagents", disabled=True)
        )

        for sub in subagents:
            name = sub.get("name", "unnamed")
            desc = sub.get("description", "").strip()
            desc_single_line = " ".join(desc.split())
            if len(desc_single_line) > 48:
                desc_single_line = desc_single_line[:45] + "..."
            label = f"[bold]{name:<16}[/bold] [dim]{desc_single_line}[/dim]"
            opt_list.add_option(Option(label, id=name))

        if subagents:
            if prev_highlighted is not None and 1 <= prev_highlighted <= len(subagents):
                opt_list.highlighted = prev_highlighted
            else:
                opt_list.highlighted = 1

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "subagents_search_input":
            if self._search_timer:
                self._search_timer.stop()
            self._search_timer = self.set_timer(
                0.2, lambda: self.filter_and_populate(event.value.strip().lower())
            )

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.action_close()
            event.prevent_default()
            event.stop()
            return

        search_input = self.query_one("#subagents_search_input", Input)
        opt_list = self.query_one("#subagents_option_list", OptionList)

        if search_input.has_focus:
            if event.key == "down":
                opt_list.action_cursor_down()
                event.prevent_default()
                event.stop()
            elif event.key == "up":
                opt_list.action_cursor_up()
                event.prevent_default()
                event.stop()
            elif event.key in ("page_down", "pagedown"):
                opt_list.action_page_down()
                event.prevent_default()
                event.stop()
            elif event.key in ("page_up", "pageup"):
                opt_list.action_page_up()
                event.prevent_default()
                event.stop()
            elif event.key == "enter":
                if opt_list.highlighted is not None and opt_list.highlighted > 0:
                    selected_opt = opt_list.get_option_at_index(opt_list.highlighted)
                    if selected_opt and selected_opt.id and selected_opt.id not in ("none", "header_subagents"):
                        self.dismiss(str(selected_opt.id))
                        event.prevent_default()
                        event.stop()
                        return
                self.dismiss(None)
                event.prevent_default()
                event.stop()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = getattr(event, "option_id", None) or getattr(getattr(event, "option", None), "id", None)
        if opt_id and opt_id not in ("none", "header_subagents"):
            self.dismiss(str(opt_id))
        else:
            self.dismiss(None)
