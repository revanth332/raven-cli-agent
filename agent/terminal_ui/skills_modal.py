"""
Modal screens for listing existing skills and creating new skills in Textual TUI.
"""

from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import OptionList, Input, TextArea, Static, Button, Label
from textual.widgets.option_list import Option

from agent.core.skills_manager import load_skills, save_skill, delete_skill


class CreateSkillModal(ModalScreen[dict | None]):
    """
    Modal dialog containing input fields to create a new skill:
    - Skill Name
    - When to Use / Description
    - Full Skill Markdown Content
    """

    CSS_PATH = "styles/skills_modal.tcss"

    def compose(self) -> ComposeResult:
        with Vertical(id="create_skill_container"):
            yield Static("✨ CREATE NEW SKILL", id="create_skill_title")
            
            yield Label("Skill Name (e.g., fast-api, nextjs-ui):", classes="form_label")
            yield Input(placeholder="Skill identifier name...", id="input_skill_name")

            yield Label("Trigger Description (When to use this skill):", classes="form_label")
            yield TextArea(id="input_skill_desc", show_line_numbers=False)

            yield Label("Full Skill Content (Markdown guidelines & instructions):", classes="form_label")
            yield TextArea(id="input_skill_content", show_line_numbers=True)

            with Horizontal(id="create_skill_actions"):
                yield Button("Cancel", id="btn_cancel_create")
                yield Button("Save Skill", id="btn_submit_create")

    def on_mount(self) -> None:
        self.query_one("#input_skill_name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel_create":
            self.dismiss(None)
        elif event.button.id == "btn_submit_create":
            self.submit_form()

    def submit_form(self) -> None:
        name_input = self.query_one("#input_skill_name", Input).value.strip()
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
            entry = save_skill(name=name_input, description=desc_input, content=content_input)
            self.dismiss(entry)
        except Exception as e:
            self.notify(f"Failed to save skill: {e}", title="Error", severity="error")


class SkillsManagerModal(ModalScreen[str | None]):
    """
    Modal screen listing all installed skills with metadata.
    Provides a button to create a new skill which launches CreateSkillModal.
    """

    CSS_PATH = "styles/skills_modal.tcss"

    def compose(self) -> ComposeResult:
        with Vertical(id="skills_modal_container"):
            yield Static("🛠️ INSTALLED AGENT SKILLS", id="skills_modal_title")
            yield Input(placeholder="Search skills... (Type 'c' to create new skill)", id="skills_search_input")
            yield OptionList(id="skills_option_list")
            with Horizontal(id="skills_modal_actions"):
                yield Button("Close", id="btn_close_skills")
                yield Button("+ Create Skill", id="btn_create_skill")

    def on_mount(self) -> None:
        self.refresh_skills()
        self.query_one("#skills_search_input", Input).focus()

    def refresh_skills(self) -> None:
        self.all_skills = load_skills()
        self.populate_options(self.all_skills)

    def populate_options(self, skills: list[dict]) -> None:
        opt_list = self.query_one("#skills_option_list", OptionList)
        opt_list.clear_options()

        if not skills:
            opt_list.add_option(Option("[#94A3B8]No skills installed yet. Click '+ Create Skill' to add one.[/#94A3B8]", id="none"))
            return

        for skill in skills:
            name = skill.get("name", "unnamed")
            path = skill.get("skill_file_path", f"skills/{name}.md")
            desc = skill.get("description", "No description provided.")
            short_desc = desc[:90] + ("..." if len(desc) > 90 else "")

            label = f"[bold cyan]{name}[/bold cyan] [dim]({path})[/dim]\n [dim white]{short_desc}[/dim white]"
            opt_list.add_option(Option(label, id=name))

        if skills:
            opt_list.highlighted = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        if not query:
            self.populate_options(self.all_skills)
            return

        filtered = [
            s for s in self.all_skills
            if query in s.get("name", "").lower() or query in s.get("description", "").lower()
        ]
        self.populate_options(filtered)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close_skills":
            self.dismiss(None)
        elif event.button.id == "btn_create_skill":
            self.open_create_skill_modal()

    def open_create_skill_modal(self) -> None:
        def on_skill_created(result: dict | None) -> None:
            if result:
                self.refresh_skills()
                name = result.get("name", "")
                self.notify(f"Skill '{name}' created successfully!", title="Skill Added", severity="information")

        self.app.push_screen(CreateSkillModal(), on_skill_created)
