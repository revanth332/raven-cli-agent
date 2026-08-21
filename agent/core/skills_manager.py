import json
import os
from pathlib import Path
from agent.utils import get_project_root


def get_skills_dir() -> Path:
    """Returns the path to the skills directory in the active project."""
    skills_dir = get_project_root() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def get_skills_json_path() -> Path:
    """Locates or determines the path for skills.json."""
    root = get_project_root()
    skills_json_in_dir = root / "skills" / "skills.json"
    skills_json_in_root = root / "skills.json"

    if skills_json_in_dir.exists():
        return skills_json_in_dir
    if skills_json_in_root.exists():
        return skills_json_in_root
    return skills_json_in_dir


def load_skills() -> list[dict]:
    """Loads all skill metadata from skills.json."""
    json_path = get_skills_json_path()
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            return []
    return []


def save_skills_metadata(skills: list[dict]) -> None:
    """Writes the skills metadata list to skills.json."""
    json_path = get_skills_json_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(skills, f, indent=2, ensure_ascii=False)


def save_skill(name: str, description: str, content: str) -> dict:
    """
    Creates or updates a skill:
    1. Writes markdown content to skills/<sanitized_name>.md
    2. Updates or appends metadata in skills.json
    """
    clean_name = name.strip().lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
    if not clean_name:
        raise ValueError("Skill name cannot be empty.")

    skills_dir = get_skills_dir()
    skill_file = skills_dir / f"{clean_name}.md"
    skill_file.write_text(content.strip() + "\n", encoding="utf-8")

    relative_path = f"skills/{clean_name}.md"
    skill_entry = {
        "name": clean_name,
        "skill_file_path": relative_path,
        "description": description.strip()
    }

    skills = load_skills()
    updated = False
    for i, s in enumerate(skills):
        if s.get("name") == clean_name:
            skills[i] = skill_entry
            updated = True
            break
    if not updated:
        skills.append(skill_entry)

    save_skills_metadata(skills)
    return skill_entry


def delete_skill(name: str, delete_file: bool = True) -> bool:
    """Deletes a skill from metadata and optionally removes its markdown file."""
    clean_name = name.strip().lower()
    skills = load_skills()
    initial_len = len(skills)
    filtered = []
    file_to_remove = None

    for s in skills:
        if s.get("name") == clean_name:
            file_to_remove = s.get("skill_file_path")
        else:
            filtered.append(s)

    if len(filtered) < initial_len:
        save_skills_metadata(filtered)
        if delete_file and file_to_remove:
            path = get_project_root() / file_to_remove
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
        return True
    return False


def build_skills_prompt_section() -> str:
    """Dynamically generates the SKILLS: section for the system prompt."""
    skills = load_skills()
    if not skills:
        return ""

    lines = [
        "SKILLS:",
        "- Skills are predefined instructions to complete a specific task. Below are the skills available for you. you just need to read the respective skill file based on the requirement using `read_file` tool.",
        "**NOTE:** Utilize 'work/' folder to execute any commands or install any packages as part of the procedure while performing the skills. Basically you need to use 'work/' as your working directory/sandbox."
    ]

    for s in skills:
        name = s.get("name", "")
        path = s.get("skill_file_path", f"skills/{name}.md")
        desc = s.get("description", "")
        lines.append("---")
        lines.append(f"name: {name}")
        lines.append(f"skill_file_path: {path}")
        lines.append(f"description: \"{desc}\"")

    return "\n".join(lines)
