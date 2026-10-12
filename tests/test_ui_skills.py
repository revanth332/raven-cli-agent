"""
Async pilot tests for TUI Skills Manager Modal.
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import OptionList

from agent.terminal_ui.skills_modal import SkillsManagerModal
from agent.core import skills_manager


class SkillsListTestApp(App):
    def compose(self) -> ComposeResult:
        yield SkillsManagerModal()


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
                # 1 header + 2 skills = 3 options
                self.assertEqual(opt_list.option_count, 3)

                # Test search filtering directly
                modal.filter_and_populate("skill-one")
                # 1 header + 1 skill = 2 options
                self.assertEqual(opt_list.option_count, 2)

                # Clear filter
                modal.filter_and_populate("")
                self.assertEqual(opt_list.option_count, 3)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
