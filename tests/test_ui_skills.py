"""
Async pilot tests for TUI Skills Manager Modal, Create Skill Modal, and Skill Detail Modal.
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Input, TextArea, OptionList

from agent.terminal_ui.skills_modal import (
    SkillsManagerModal,
    CreateSkillModal,
    SkillDetailModal,
    ConfirmDeleteModal,
)
from agent.core import skills_manager


class SkillsListTestApp(App):
    def compose(self) -> ComposeResult:
        yield SkillsManagerModal()


class CreateSkillTestApp(App):
    def compose(self) -> ComposeResult:
        yield CreateSkillModal()


class TestUISkills(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.global_temp_dir = Path(tempfile.mkdtemp())
        self.orig_get_root = skills_manager.get_project_root
        self.orig_get_global = skills_manager.get_global_skills_dir

        skills_manager.get_project_root = lambda: self.temp_dir
        skills_manager.get_global_skills_dir = lambda: self.global_temp_dir

    def tearDown(self):
        skills_manager.get_project_root = self.orig_get_root
        skills_manager.get_global_skills_dir = self.orig_get_global
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.global_temp_dir, ignore_errors=True)

    def test_skills_manager_modal_listing(self):
        skills_manager.save_skill(
            name="skill-one",
            description="First skill description",
            content="Content 1",
            scope="project",
        )
        skills_manager.save_skill(
            name="skill-two",
            description="Second skill description",
            content="Content 2",
            scope="global",
        )

        app = SkillsListTestApp()

        async def run_test():
            async with app.run_test() as pilot:
                modal = app.query_one(SkillsManagerModal)
                self.assertIsNotNone(modal)
                opt_list = modal.query_one("#skills_option_list", OptionList)
                self.assertEqual(opt_list.option_count, 2)

                # Test search filtering directly
                modal.filter_and_populate("skill-one")
                self.assertEqual(opt_list.option_count, 1)

                # Clear filter
                modal.filter_and_populate("")
                self.assertEqual(opt_list.option_count, 2)

        asyncio.run(run_test())

    def test_create_skill_modal_submission(self):
        app = CreateSkillTestApp()

        async def run_test():
            async with app.run_test() as pilot:
                modal = app.query_one(CreateSkillModal)
                self.assertIsNotNone(modal)

                name_input = modal.query_one("#input_skill_name", Input)
                desc_input = modal.query_one("#input_skill_desc", TextArea)
                content_input = modal.query_one("#input_skill_content", TextArea)

                name_input.value = "kubernetes-ops"
                desc_input.text = "When writing k8s yaml or helm charts."
                content_input.text = "# K8s Guidelines\nAlways specify CPU and memory limits."

                modal.submit_form()
                await pilot.pause()

                # Verify skill saved
                skills = skills_manager.load_skills()
                self.assertEqual(len(skills), 1)
                self.assertEqual(skills[0]["name"], "kubernetes-ops")
                self.assertEqual(skills[0]["skill_file_path"], "skills/kubernetes-ops.md")

                md_path = self.temp_dir / "skills" / "kubernetes-ops.md"
                self.assertTrue(md_path.exists())
                self.assertIn("Always specify CPU and memory limits.", md_path.read_text(encoding="utf-8"))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
