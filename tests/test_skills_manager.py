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

    def test_save_and_load_skill(self):
        name = "fastapi-expert"
        desc = "Use this skill when developing or debugging FastAPI endpoints."
        content = "# FastAPI Skill Guidelines\n\nAlways use Pydantic v2 schemas."

        saved = skills_manager.save_skill(name=name, description=desc, content=content, scope="project")
        self.assertEqual(saved["name"], "fastapi-expert")
        self.assertEqual(saved["skill_file_path"], "skills/fastapi-expert.md")
        self.assertEqual(saved["description"], desc)
        self.assertEqual(saved["scope"], "project")

        # Verify physical markdown file was written with frontmatter
        md_file = self.temp_dir / "skills" / "fastapi-expert.md"
        self.assertTrue(md_file.exists())
        file_text = md_file.read_text(encoding="utf-8")
        self.assertIn("name: fastapi-expert", file_text)
        self.assertIn("Always use Pydantic v2 schemas.", file_text)

        # Verify discover/load skills
        skills = skills_manager.load_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["name"], "fastapi-expert")

    def test_global_and_project_precedence(self):
        # Save a global skill
        skills_manager.save_skill(
            name="shared-util",
            description="Global version",
            content="Global content",
            scope="global",
        )
        # Save a unique global skill
        skills_manager.save_skill(
            name="global-only",
            description="Global only desc",
            content="Global only content",
            scope="global",
        )
        # Save a project skill with same name as global shared-util
        skills_manager.save_skill(
            name="shared-util",
            description="Project override version",
            content="Project override content",
            scope="project",
        )

        all_skills = skills_manager.discover_skills()
        self.assertEqual(len(all_skills), 2)

        skill_map = {s["name"]: s for s in all_skills}
        self.assertIn("global-only", skill_map)
        self.assertEqual(skill_map["global-only"]["scope"], "global")

        self.assertIn("shared-util", skill_map)
        self.assertEqual(skill_map["shared-util"]["scope"], "project")
        self.assertEqual(skill_map["shared-util"]["description"], "Project override version")

    def test_toggle_skill(self):
        skills_manager.save_skill(
            name="toggle-test",
            description="Toggle desc",
            content="Instruction body",
            scope="project",
            enabled=True,
        )
        skill = skills_manager.get_skill("toggle-test")
        self.assertTrue(skill["enabled"])

        # Toggle to disabled
        skills_manager.toggle_skill("toggle-test", enabled=False)
        skill = skills_manager.get_skill("toggle-test")
        self.assertFalse(skill["enabled"])

        # In prompt section, disabled skills should be omitted
        prompt_sec = skills_manager.build_skills_prompt_section()
        self.assertNotIn("toggle-test", prompt_sec)

        # Toggle back to enabled
        skills_manager.toggle_skill("toggle-test", enabled=True)
        skill = skills_manager.get_skill("toggle-test")
        self.assertTrue(skill["enabled"])
        prompt_sec = skills_manager.build_skills_prompt_section()
        self.assertIn("toggle-test", prompt_sec)

    def test_build_skills_prompt_section(self):
        skills_manager.save_skill(
            name="test-skill",
            description="A test skill trigger.",
            content="Instructions...",
            scope="project",
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
            content="Delete me",
            scope="project",
        )
        self.assertEqual(len(skills_manager.load_skills()), 1)
        md_file = self.temp_dir / "skills" / "to-delete.md"
        self.assertTrue(md_file.exists())

        deleted = skills_manager.delete_skill("to-delete")
        self.assertTrue(deleted)
        self.assertEqual(len(skills_manager.load_skills()), 0)
        self.assertFalse(md_file.exists())

    def test_path_traversal_protection(self):
        with self.assertRaises(ValueError):
            skills_manager.save_skill(
                name="../../malicious",
                description="desc",
                content="evil",
            )

    def test_migration_legacy_skills_json(self):
        skills_dir = self.temp_dir / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        json_path = skills_dir / "skills.json"
        
        legacy_data = [
            {
                "name": "migrated-skill",
                "skill_file_path": "skills/migrated-skill.md",
                "description": "Migrated description from JSON"
            }
        ]
        json_path.write_text(json.dumps(legacy_data), encoding="utf-8")
        (skills_dir / "migrated-skill.md").write_text("# Original body content", encoding="utf-8")

        skills = skills_manager.discover_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["name"], "migrated-skill")
        self.assertEqual(skills[0]["description"], "Migrated description from JSON")
        self.assertIn("# Original body content", skills[0]["content"])

        # Check backup file created
        self.assertTrue((skills_dir / "skills.json.bak").exists())
        self.assertFalse(json_path.exists())


if __name__ == "__main__":
    unittest.main()
