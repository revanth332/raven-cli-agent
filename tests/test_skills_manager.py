import unittest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch

from agent.core import skills_manager


class TestSkillsManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.orig_get_root = skills_manager.get_project_root
        skills_manager.get_project_root = lambda: self.temp_dir

    def tearDown(self):
        skills_manager.get_project_root = self.orig_get_root
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_skill(self):
        name = "fastapi-expert"
        desc = "Use this skill when developing or debugging FastAPI endpoints."
        content = "# FastAPI Skill Guidelines\n\nAlways use Pydantic v2 schemas."

        saved = skills_manager.save_skill(name=name, description=desc, content=content)
        self.assertEqual(saved["name"], "fastapi-expert")
        self.assertEqual(saved["skill_file_path"], "skills/fastapi-expert.md")
        self.assertEqual(saved["description"], desc)

        # Verify physical markdown file was written
        md_file = self.temp_dir / "skills" / "fastapi-expert.md"
        self.assertTrue(md_file.exists())
        self.assertIn("Always use Pydantic v2 schemas.", md_file.read_text(encoding="utf-8"))

        # Verify json loading
        skills = skills_manager.load_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["name"], "fastapi-expert")

    def test_build_skills_prompt_section(self):
        skills_manager.save_skill(
            name="test-skill",
            description="A test skill trigger.",
            content="Instructions..."
        )
        prompt_sec = skills_manager.build_skills_prompt_section()
        self.assertIn("SKILLS:", prompt_sec)
        self.assertIn("name: test-skill", prompt_sec)
        self.assertIn("skill_file_path: skills/test-skill.md", prompt_sec)
        self.assertIn('description: "A test skill trigger."', prompt_sec)

    def test_delete_skill(self):
        skills_manager.save_skill(
            name="to-delete",
            description="Will be deleted",
            content="Delete me"
        )
        self.assertEqual(len(skills_manager.load_skills()), 1)
        md_file = self.temp_dir / "skills" / "to-delete.md"
        self.assertTrue(md_file.exists())

        deleted = skills_manager.delete_skill("to-delete")
        self.assertTrue(deleted)
        self.assertEqual(len(skills_manager.load_skills()), 0)
        self.assertFalse(md_file.exists())


if __name__ == "__main__":
    unittest.main()
