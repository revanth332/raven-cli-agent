"""
Modal screen for viewing discovered agent skills in Textual TUI.
"""

from typing import Any, Dict, List, Optional
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import OptionList, Input, Static
from textual.widgets.option_list import Option

from agent.core.skills_manager import load_skills


class SkillsManagerModal(ModalScreen[str | None]):
    """
    Modal screen listing all discovered skills (global + project).
    Provides debounced search and clean viewer layout.
    """

    CSS_PATH = "styles/skills_modal.tcss"

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.all_skills: List[Dict[str, Any]] = []
        self.filtered_skills: List[Dict[str, Any]] = []
        self._search_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="skills_modal_container"):
            with Horizontal(id="skills_header_row"):
                yield Static("Skills", id="skills_modal_title")
                yield Static("esc", id="skills_close_hint")
            yield Input(
                placeholder="Search skills...",
                id="skills_search_input",
            )
            yield OptionList(id="skills_option_list")

    def on_mount(self) -> None:
        self.refresh_skills()
        self.query_one("#skills_search_input", Input).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def refresh_skills(self) -> None:
        self.all_skills = load_skills(include_disabled=False)
        search_val = self.query_one("#skills_search_input", Input).value.strip().lower()
        self.filter_and_populate(search_val)

    def filter_and_populate(self, query: str = "") -> None:
        if not query:
            self.filtered_skills = list(self.all_skills)
        else:
            self.filtered_skills = [
                s
                for s in self.all_skills
                if query in s.get("name", "").lower()
                or query in s.get("description", "").lower()
                or query in s.get("scope", "").lower()
            ]
        self.populate_options(self.filtered_skills)

    def populate_options(self, skills: List[Dict[str, Any]]) -> None:
        opt_list = self.query_one("#skills_option_list", OptionList)
        prev_highlighted = opt_list.highlighted
        opt_list.clear_options()

        if not skills:
            opt_list.add_option(
                Option("[dim #71717a]No matching skills found[/dim #71717a]", id="none", disabled=True)
            )
            return

        opt_list.add_option(
            Option("[bold #10B981]Skills[/bold #10B981]", id="header_skills", disabled=True)
        )

        for skill in skills:
            name = skill.get("name", "unnamed")
            desc = skill.get("description", "").strip()
            desc_single_line = " ".join(desc.split())
            if len(desc_single_line) > 48:
                desc_single_line = desc_single_line[:45] + "..."
            label = f"[bold]{name:<16}[/bold] [dim]{desc_single_line}[/dim]"
            opt_list.add_option(Option(label, id=name))

        if skills:
            if prev_highlighted is not None and 1 <= prev_highlighted <= len(skills):
                opt_list.highlighted = prev_highlighted
            else:
                opt_list.highlighted = 1

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "skills_search_input":
            if self._search_timer:
                self._search_timer.stop()
            self._search_timer = self.set_timer(
                0.2, lambda: self.filter_and_populate(event.value.strip().lower())
            )

    def on_key(self, event: events.Key) -> None:
        search_input = self.query_one("#skills_search_input", Input)
        opt_list = self.query_one("#skills_option_list", OptionList)

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
                    if selected_opt and selected_opt.id and selected_opt.id not in ("none", "header_skills"):
                        self.dismiss(str(selected_opt.id))
                        event.prevent_default()
                        event.stop()
                        return
                self.dismiss(None)
                event.prevent_default()
                event.stop()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id and event.option_id not in ("none", "header_skills"):
            self.dismiss(str(event.option_id))
        else:
            self.dismiss(None)

