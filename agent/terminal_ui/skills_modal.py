"""
Modal screens for listing, viewing, editing, creating, and deleting skills in Textual TUI.
"""

from typing import Any, Dict, List, Optional
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Input, TextArea, Static, Button, Label, Select
from textual.widgets.option_list import Option

from agent.core.skills_manager import (
    load_skills,
    discover_skills,
    get_skill,
    save_skill,
    delete_skill,
    toggle_skill,
)


class ConfirmDeleteModal(ModalScreen[bool]):
    """Confirmation modal before deleting a skill."""

    CSS_PATH = "styles/skills_modal.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, skill_name: str, scope: str = "project", skill_type: str = "file") -> None:
        super().__init__()
        self.skill_name = skill_name
        self.scope = scope
        self.skill_type = skill_type

    def compose(self) -> ComposeResult:
        type_desc = "skill folder and all contained files" if self.skill_type == "folder" else "markdown file"
        with Vertical(id="confirm_delete_container"):
            yield Static("⚠️ CONFIRM DELETION", id="confirm_delete_title")
            yield Static(
                f"Are you sure you want to delete skill [bold cyan]'{self.skill_name}'[/bold cyan] "
                f"from [bold #38BDF8]{self.scope}[/bold #38BDF8] scope?\n\n"
                f"[dim]This action permanently removes the {type_desc} and cannot be undone.[/dim]",
                id="confirm_delete_message",
            )
            with Horizontal(id="confirm_delete_actions"):
                yield Button("Cancel", id="btn_cancel_delete")
                yield Button("Delete Skill", id="btn_confirm_delete", variant="error")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_confirm_delete":
            self.dismiss(True)
        else:
            self.dismiss(False)


class CreateSkillModal(ModalScreen[dict | None]):
    """
    Modal dialog containing input fields to create a new skill:
    - Skill Name
    - Scope (Project-Local vs Global)
    - When to Use / Description
    - Full Skill Markdown Content
    """

    CSS_PATH = "styles/skills_modal.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+s", "save", "Save Skill", priority=True),
    ]

    def compose(self) -> ComposeResult:
        scope_options = [
            ("Project Local (./skills)", "project"),
            ("User Global (~/.raven/skills)", "global"),
        ]
        format_options = [
            ("Single File (.md)", "file"),
            ("Multi-File Folder (SKILL.md)", "folder"),
        ]

        with Vertical(id="create_skill_container"):
            yield Static("✨ CREATE NEW SKILL", id="create_skill_title")

            with Horizontal(classes="form_row"):
                with Vertical(classes="form_col_flex"):
                    yield Label("Skill Name (e.g., fastapi-expert, animate):", classes="form_label")
                    yield Input(placeholder="Skill identifier name...", id="input_skill_name")
                with Vertical(classes="form_col_fixed"):
                    yield Label("Target Scope:", classes="form_label")
                    yield Select(scope_options, value="project", id="select_skill_scope", allow_blank=False)
                with Vertical(classes="form_col_fixed"):
                    yield Label("Format:", classes="form_label")
                    yield Select(format_options, value="file", id="select_skill_format", allow_blank=False)

            yield Label("Trigger Description (When to use this skill):", classes="form_label")
            yield TextArea(id="input_skill_desc", show_line_numbers=False)

            yield Label("Full Skill Content (Markdown guidelines & instructions):", classes="form_label")
            yield TextArea(id="input_skill_content", show_line_numbers=True)

            with Horizontal(id="create_skill_actions"):
                yield Button("Cancel", id="btn_cancel_create")
                yield Button("Save Skill", id="btn_submit_create", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#input_skill_name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.submit_form()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel_create":
            self.dismiss(None)
        elif event.button.id == "btn_submit_create":
            self.submit_form()

    def submit_form(self) -> None:
        name_input = self.query_one("#input_skill_name", Input).value.strip()
        scope_select = self.query_one("#select_skill_scope", Select)
        scope = scope_select.value if scope_select.value != Select.BLANK else "project"
        format_select = self.query_one("#select_skill_format", Select)
        is_folder = (format_select.value == "folder") if format_select.value != Select.BLANK else False
        desc_input = self.query_one("#input_skill_desc", TextArea).text.strip()
        content_input = self.query_one("#input_skill_content", TextArea).text.strip()

        if not name_input:
            self.notify("Please enter a skill name.", title="Validation Error", severity="error")
            self.query_one("#input_skill_name", Input).focus()
            return

        if not desc_input:
            self.notify("Please enter a trigger description.", title="Validation Error", severity="error")
            self.query_one("#input_skill_desc", TextArea).focus()
            return

        if not content_input:
            self.notify("Please enter the skill instructions content.", title="Validation Error", severity="error")
            self.query_one("#input_skill_content", TextArea).focus()
            return

        try:
            entry = save_skill(
                name=name_input,
                description=desc_input,
                content=content_input,
                scope=scope,
                as_folder=is_folder,
            )
            self.dismiss(entry)
        except Exception as e:
            self.notify(f"Failed to save skill: {e}", title="Error", severity="error")


class SkillDetailModal(ModalScreen[dict | None]):
    """
    Modal screen for viewing and inline-editing an existing skill's description and content.
    """

    CSS_PATH = "styles/skills_modal.tcss"

    BINDINGS = [
        Binding("escape", "cancel", "Close", priority=True),
        Binding("ctrl+s", "save", "Save Changes", priority=True),
    ]

    def __init__(self, skill: Dict[str, Any]) -> None:
        super().__init__()
        self.skill = skill
        self.skill_name = skill.get("name", "")
        self.scope = skill.get("scope", "project")
        self.is_enabled = skill.get("enabled", True)

    def compose(self) -> ComposeResult:
        scope_badge = f"[#38BDF8][{self.scope.upper()}][/#38BDF8]" if self.scope == "project" else f"[#A855F7][{self.scope.upper()}][/#A855F7]"
        skill_type = self.skill.get("skill_type", "file")
        type_badge = "[#F59E0B][FOLDER][/#F59E0B]" if skill_type == "folder" else "[#6EE7B7][FILE][/#6EE7B7]"
        status_badge = "[#22C55E][ENABLED][/#22C55E]" if self.is_enabled else "[#64748B][DISABLED][/#64748B]"

        path_info = f"File: {self.skill.get('skill_file_path', '')}"
        if skill_type == "folder" and self.skill.get("root_dir"):
            path_info += f"  |  Dir: {self.skill.get('root_dir')}"

        with Vertical(id="skill_detail_container"):
            yield Static(
                f"📝 SKILL: [bold cyan]{self.skill_name}[/bold cyan]  {scope_badge}  {type_badge}  {status_badge}",
                id="skill_detail_title",
            )
            yield Static(f"[dim]{path_info}[/dim]", id="skill_detail_path")

            yield Label("Trigger Description:", classes="form_label")
            yield TextArea(self.skill.get("description", ""), id="edit_skill_desc", show_line_numbers=False)

            yield Label("Markdown Instructions Body:", classes="form_label")
            yield TextArea(self.skill.get("content", ""), id="edit_skill_content", show_line_numbers=True)

            with Horizontal(id="skill_detail_actions"):
                yield Button("Close", id="btn_cancel_detail")
                yield Button(
                    "Disable Skill" if self.is_enabled else "Enable Skill",
                    id="btn_toggle_detail",
                )
                yield Button("Delete", id="btn_delete_detail", variant="error")
                yield Button("Save Changes", id="btn_save_detail", variant="primary")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_changes()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel_detail":
            self.dismiss(None)
        elif event.button.id == "btn_save_detail":
            self.save_changes()
        elif event.button.id == "btn_toggle_detail":
            self.toggle_status()
        elif event.button.id == "btn_delete_detail":
            self.prompt_delete()

    def toggle_status(self) -> None:
        new_state = not self.is_enabled
        success = toggle_skill(self.skill_name, new_state, scope=self.scope)
        if success:
            self.is_enabled = new_state
            self.skill["enabled"] = new_state
            btn = self.query_one("#btn_toggle_detail", Button)
            btn.label = "Disable Skill" if self.is_enabled else "Enable Skill"
            self.notify(f"Skill '{self.skill_name}' {'enabled' if new_state else 'disabled'}.")
        else:
            self.notify("Failed to toggle skill status.", severity="error")

    def prompt_delete(self) -> None:
        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                deleted = delete_skill(self.skill_name, scope=self.scope)
                if deleted:
                    self.notify(f"Skill '{self.skill_name}' deleted.", severity="information")
                    self.dismiss({"action": "deleted", "name": self.skill_name})
                else:
                    self.notify(f"Failed to delete skill '{self.skill_name}'.", severity="error")

        skill_type = self.skill.get("skill_type", "file")
        self.app.push_screen(ConfirmDeleteModal(self.skill_name, self.scope, skill_type=skill_type), on_confirmed)

    def save_changes(self) -> None:
        desc_input = self.query_one("#edit_skill_desc", TextArea).text.strip()
        content_input = self.query_one("#edit_skill_content", TextArea).text.strip()

        if not desc_input:
            self.notify("Description cannot be empty.", severity="error")
            return
        if not content_input:
            self.notify("Skill content cannot be empty.", severity="error")
            return

        try:
            updated = save_skill(
                name=self.skill_name,
                description=desc_input,
                content=content_input,
                scope=self.scope,
                enabled=self.is_enabled,
                triggers=self.skill.get("triggers"),
            )
            self.notify(f"Skill '{self.skill_name}' updated successfully!", severity="information")
            self.dismiss(updated)
        except Exception as e:
            self.notify(f"Failed to save changes: {e}", severity="error")


class SkillsManagerModal(ModalScreen[str | None]):
    """
    Modal screen listing all discovered skills (global + project).
    Provides debounced search, badges, inline editing, toggle, and deletion.
    """

    CSS_PATH = "styles/skills_modal.tcss"

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("c", "create_skill", "Create Skill", priority=False),
        Binding("e", "edit_selected", "Edit Skill", priority=False),
        Binding("space", "toggle_selected", "Toggle Skill", priority=False),
        Binding("d", "delete_selected", "Delete Skill", priority=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.all_skills: List[Dict[str, Any]] = []
        self.filtered_skills: List[Dict[str, Any]] = []
        self._search_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="skills_modal_container"):
            yield Static("🛠️ INSTALLED AGENT SKILLS", id="skills_modal_title")
            yield Input(
                placeholder="Search skills... (Type 'c' to create, 'Space' to toggle, 'e'/Enter to edit)",
                id="skills_search_input",
            )
            yield OptionList(id="skills_option_list")
            yield Static(
                "[bold cyan][c][/bold cyan] New  |  "
                "[bold cyan][Enter/e][/bold cyan] Edit/Preview  |  "
                "[bold cyan][Space][/bold cyan] Toggle  |  "
                "[bold cyan][d][/bold cyan] Delete  |  "
                "[bold cyan][Esc][/bold cyan] Close",
                id="skills_hotkeys_hint",
            )
            with Horizontal(id="skills_modal_actions"):
                yield Button("Close", id="btn_close_skills")
                yield Button("Toggle Enable", id="btn_toggle_skills")
                yield Button("Edit / Preview", id="btn_edit_skills")
                yield Button("Delete", id="btn_delete_skills", variant="error")
                yield Button("+ Create Skill", id="btn_create_skill", variant="primary")

    def on_mount(self) -> None:
        self.refresh_skills()
        self.query_one("#skills_search_input", Input).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def refresh_skills(self) -> None:
        self.all_skills = load_skills(include_disabled=True)
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
                Option("[#94A3B8]No matching skills found. Click '+ Create Skill' or press 'c' to add one.[/#94A3B8]", id="none")
            )
            return

        for skill in skills:
            name = skill.get("name", "unnamed")
            scope = skill.get("scope", "project")
            skill_type = skill.get("skill_type", "file")
            enabled = skill.get("enabled", True)
            path = skill.get("skill_file_path", f"skills/{name}.md")
            desc = skill.get("description", "No description provided.")
            short_desc = desc[:80] + ("..." if len(desc) > 80 else "")

            scope_badge = "[#38BDF8][Project][/#38BDF8]" if scope == "project" else "[#A855F7][Global][/#A855F7]"
            type_badge = "[#F59E0B][Folder][/#F59E0B]" if skill_type == "folder" else "[#6EE7B7][File][/#6EE7B7]"
            status_badge = "[#22C55E][Enabled][/#22C55E]" if enabled else "[#64748B][Disabled][/#64748B]"

            label = (
                f"[bold cyan]{name:<20}[/bold cyan]  {scope_badge}  {type_badge}  {status_badge}  [dim]({path})[/dim]\n"
                f"   [dim white]{short_desc}[/dim white]"
            )
            opt_list.add_option(Option(label, id=name))

        if skills:
            if prev_highlighted is not None and prev_highlighted < len(skills):
                opt_list.highlighted = prev_highlighted
            else:
                opt_list.highlighted = 0

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
                self.action_edit_selected()
                event.prevent_default()
                event.stop()

    def get_selected_skill(self) -> Optional[Dict[str, Any]]:
        opt_list = self.query_one("#skills_option_list", OptionList)
        if opt_list.highlighted is None or not self.filtered_skills:
            return None
        if 0 <= opt_list.highlighted < len(self.filtered_skills):
            return self.filtered_skills[opt_list.highlighted]
        return None

    def action_create_skill(self) -> None:
        search_input = self.query_one("#skills_search_input", Input)
        if search_input.has_focus and search_input.value:
            return
        self.open_create_skill_modal()

    def action_edit_selected(self) -> None:
        skill = self.get_selected_skill()
        if skill:
            self.open_detail_modal(skill)

    def action_toggle_selected(self) -> None:
        search_input = self.query_one("#skills_search_input", Input)
        if search_input.has_focus and search_input.value:
            return
        skill = self.get_selected_skill()
        if not skill:
            return

        name = skill.get("name", "")
        new_state = not skill.get("enabled", True)
        if toggle_skill(name, new_state, scope=skill.get("scope")):
            skill["enabled"] = new_state
            self.notify(f"Skill '{name}' {'enabled' if new_state else 'disabled'}.")
            self.populate_options(self.filtered_skills)
        else:
            self.notify(f"Failed to toggle skill '{name}'.", severity="error")

    def action_delete_selected(self) -> None:
        search_input = self.query_one("#skills_search_input", Input)
        if search_input.has_focus and search_input.value:
            return
        skill = self.get_selected_skill()
        if not skill:
            return

        name = skill.get("name", "")
        scope = skill.get("scope", "project")
        skill_type = skill.get("skill_type", "file")

        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                if delete_skill(name, scope=scope):
                    self.notify(f"Skill '{name}' deleted.", severity="information")
                    self.refresh_skills()
                else:
                    self.notify(f"Failed to delete skill '{name}'.", severity="error")

        self.app.push_screen(ConfirmDeleteModal(name, scope, skill_type=skill_type), on_confirmed)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id and event.option_id != "none":
            skill = get_skill(str(event.option_id))
            if skill:
                self.open_detail_modal(skill)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close_skills":
            self.dismiss(None)
        elif event.button.id == "btn_create_skill":
            self.open_create_skill_modal()
        elif event.button.id == "btn_edit_skills":
            self.action_edit_selected()
        elif event.button.id == "btn_toggle_skills":
            skill = self.get_selected_skill()
            if skill:
                name = skill.get("name", "")
                new_state = not skill.get("enabled", True)
                if toggle_skill(name, new_state, scope=skill.get("scope")):
                    skill["enabled"] = new_state
                    self.notify(f"Skill '{name}' {'enabled' if new_state else 'disabled'}.")
                    self.populate_options(self.filtered_skills)
        elif event.button.id == "btn_delete_skills":
            self.action_delete_selected()

    def open_create_skill_modal(self) -> None:
        def on_skill_created(result: dict | None) -> None:
            if result:
                self.refresh_skills()
                name = result.get("name", "")
                self.notify(f"Skill '{name}' created successfully!", title="Skill Added", severity="information")

        self.app.push_screen(CreateSkillModal(), on_skill_created)

    def open_detail_modal(self, skill: Dict[str, Any]) -> None:
        def on_detail_closed(result: dict | None) -> None:
            self.refresh_skills()

        self.app.push_screen(SkillDetailModal(skill), on_detail_closed)

