"""
Core Skills Manager for Raven CLI Agent.
Supports YAML frontmatter in Markdown files with dual-scope discovery (global and project-local).
"""

import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from agent.utils import get_project_root


FRONTMATTER_REGEX = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$", re.DOTALL)


def get_project_skills_dir() -> Path:
    """Returns the path to the project-local skills directory."""
    skills_dir = get_project_root() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def get_global_skills_dir() -> Path:
    """Returns the path to the user's global skills directory in ~/.raven/skills."""
    skills_dir = Path.home() / ".raven" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def get_skills_dir() -> Path:
    """Backward compatibility alias for project skills directory."""
    return get_project_skills_dir()


def sanitize_skill_name(name: str) -> str:
    """Sanitizes skill name into lowercase alphanumeric identifier with hyphens/underscores."""
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean


def parse_frontmatter(raw_text: str) -> tuple[Dict[str, Any], str]:
    """
    Zero-dependency YAML frontmatter parser.
    Extracts key-value pairs (including booleans, strings, and lists) and markdown body.
    """
    match = FRONTMATTER_REGEX.match(raw_text.strip())
    if not match:
        return {}, raw_text

    header, body = match.groups()
    meta: Dict[str, Any] = {}
    current_key = None
    current_list: Optional[List[str]] = None

    for line in header.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Check for list item under current_key
        if line.startswith("  - ") or line.startswith("    - ") or (stripped.startswith("- ") and current_key):
            val = stripped[2:].strip().strip("\"'")
            if current_list is not None:
                current_list.append(val)
            continue

        # Check for key: value
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            current_key = key
            if not val:
                current_list = []
                meta[key] = current_list
            else:
                current_list = None
                val_lower = val.lower()
                if val_lower in ("true", "yes", "1"):
                    meta[key] = True
                elif val_lower in ("false", "no", "0"):
                    meta[key] = False
                elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    meta[key] = val[1:-1].replace('\\"', '"')
                else:
                    meta[key] = val

    return meta, body


def dump_frontmatter(metadata: Dict[str, Any], content: str) -> str:
    """Generates standard Markdown string prefixed with YAML frontmatter."""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif isinstance(value, str):
            escaped = value.replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append(content.strip())
    return "\n".join(lines) + "\n"


def parse_skill_file(path: Path, scope: str = "project") -> Optional[Dict[str, Any]]:
    """
    Parses a single skill markdown file with frontmatter.
    Returns metadata dictionary or None if invalid.
    """
    if not path.is_file() or path.suffix.lower() != ".md":
        return None

    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    meta, body = parse_frontmatter(raw_text)

    name = meta.get("name") or path.stem.lower()
    name = sanitize_skill_name(name)
    description = meta.get("description", "")
    triggers = meta.get("triggers", [])
    if isinstance(triggers, str):
        triggers = [triggers]
    enabled = meta.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() not in ("false", "0", "no")

    try:
        project_root = get_project_root()
        if scope == "project" or path.is_relative_to(project_root):
            rel_path = str(path.relative_to(project_root)).replace("\\", "/")
        else:
            rel_path = str(path).replace("\\", "/")
    except Exception:
        rel_path = str(path).replace("\\", "/")

    return {
        "name": name,
        "description": description,
        "triggers": triggers,
        "enabled": enabled,
        "scope": scope,
        "skill_file_path": rel_path,
        "full_path": str(path.resolve()),
        "content": body.strip(),
        "raw_markdown": raw_text,
    }


def migrate_legacy_skills_json() -> None:
    """
    Checks if skills.json exists, merges metadata into respective markdown files as YAML frontmatter,
    and renames skills.json to skills.json.bak.
    """
    import json

    try:
        root = get_project_root()
    except Exception:
        return

    possible_paths = [root / "skills" / "skills.json", root / "skills.json"]

    for json_path in possible_paths:
        if not json_path.exists():
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                skills_dir = get_project_skills_dir()
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    name = sanitize_skill_name(item.get("name", ""))
                    if not name:
                        continue
                    desc = item.get("description", "")
                    rel_file = item.get("skill_file_path", f"skills/{name}.md")
                    target_file = root / rel_file
                    if not target_file.exists():
                        target_file = skills_dir / f"{name}.md"

                    body = ""
                    triggers = item.get("triggers", [])
                    enabled = item.get("enabled", True)
                    if target_file.exists():
                        raw = target_file.read_text(encoding="utf-8")
                        existing_meta, existing_body = parse_frontmatter(raw)
                        body = existing_body if existing_meta else raw
                        if not desc and existing_meta.get("description"):
                            desc = existing_meta.get("description")

                    metadata = {
                        "name": name,
                        "description": desc,
                        "enabled": enabled,
                    }
                    if triggers:
                        metadata["triggers"] = triggers

                    full_md = dump_frontmatter(metadata, body)
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_text(full_md, encoding="utf-8")

            bak_path = json_path.with_name(json_path.name + ".bak")
            json_path.rename(bak_path)
        except Exception:
            pass


def discover_skills(include_disabled: bool = True) -> List[Dict[str, Any]]:
    """
    Scans both user global (~/.raven/skills/) and project-local (./skills/) directories.
    Project-local skills override global skills with the same name.
    """
    migrate_legacy_skills_json()

    skills_map: Dict[str, Dict[str, Any]] = {}

    # 1. Scan User Global Scope
    try:
        global_dir = get_global_skills_dir()
        if global_dir.exists():
            for file in sorted(global_dir.glob("*.md")):
                skill = parse_skill_file(file, scope="global")
                if skill and skill.get("name"):
                    skills_map[skill["name"]] = skill
    except Exception:
        pass

    # 2. Scan Project Local Scope (takes precedence)
    try:
        project_dir = get_project_skills_dir()
        if project_dir.exists():
            for file in sorted(project_dir.glob("*.md")):
                skill = parse_skill_file(file, scope="project")
                if skill and skill.get("name"):
                    skills_map[skill["name"]] = skill
    except Exception:
        pass

    results = list(skills_map.values())
    results.sort(key=lambda s: s.get("name", ""))

    if not include_disabled:
        results = [s for s in results if s.get("enabled", True)]

    return results


def load_skills(include_disabled: bool = True) -> List[Dict[str, Any]]:
    """Loads all discovered skills (alias for discover_skills)."""
    return discover_skills(include_disabled=include_disabled)


def get_skill(name: str) -> Optional[Dict[str, Any]]:
    """Retrieves a skill by name (project overrides global)."""
    clean_name = sanitize_skill_name(name)
    all_skills = discover_skills(include_disabled=True)
    for skill in all_skills:
        if skill.get("name") == clean_name:
            return skill
    return None


def save_skill(
    name: str,
    description: str,
    content: str,
    scope: str = "project",
    enabled: bool = True,
    triggers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Saves a skill into the target scope directory (global or project).
    Generates standard YAML frontmatter in Markdown.
    """
    clean_name = sanitize_skill_name(name)
    if not clean_name:
        raise ValueError("Skill name cannot be empty.")

    target_dir = get_project_skills_dir() if scope.lower() == "project" else get_global_skills_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = (target_dir / f"{clean_name}.md").resolve()

    # Path traversal validation
    if not str(file_path).startswith(str(target_dir.resolve())):
        raise ValueError("Invalid skill path traversal attempt.")

    metadata = {
        "name": clean_name,
        "description": description.strip(),
        "enabled": enabled,
    }
    if triggers:
        metadata["triggers"] = triggers

    full_md = dump_frontmatter(metadata, content)
    file_path.write_text(full_md, encoding="utf-8")

    parsed = parse_skill_file(file_path, scope=scope.lower())
    if not parsed:
        raise RuntimeError(f"Failed to parse written skill file at {file_path}")
    return parsed


def delete_skill(name: str, scope: Optional[str] = None) -> bool:
    """
    Deletes a skill markdown file from the target scope or wherever it exists.
    """
    clean_name = sanitize_skill_name(name)
    if not clean_name:
        return False

    deleted = False
    scopes_to_check = [scope.lower()] if scope else ["project", "global"]

    for sc in scopes_to_check:
        target_dir = get_project_skills_dir() if sc == "project" else get_global_skills_dir()
        file_path = (target_dir / f"{clean_name}.md").resolve()
        if str(file_path).startswith(str(target_dir.resolve())) and file_path.exists():
            try:
                file_path.unlink()
                deleted = True
            except Exception:
                pass
            if deleted:
                break

    return deleted


def toggle_skill(name: str, enabled: bool, scope: Optional[str] = None) -> bool:
    """
    Toggles the enabled status of a skill without modifying its instructions.
    """
    clean_name = sanitize_skill_name(name)
    skill = get_skill(clean_name)
    if not skill:
        return False

    full_path_str = skill.get("full_path")
    if not full_path_str:
        return False

    file_path = Path(full_path_str)
    if not file_path.exists():
        return False

    raw_text = file_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw_text)
    meta["enabled"] = enabled
    if not meta.get("name"):
        meta["name"] = clean_name
    if not meta.get("description"):
        meta["description"] = skill.get("description", "")

    new_content = dump_frontmatter(meta, body)
    file_path.write_text(new_content, encoding="utf-8")
    return True


def build_skills_prompt_section() -> str:
    """Dynamically generates the SKILLS: section for the system prompt from all enabled skills."""
    skills = discover_skills(include_disabled=False)
    if not skills:
        return ""

    lines = [
        "SKILLS:",
        "- Skills are predefined instructions to complete a specific task. Below are the skills available for you. you just need to read the respective skill file based on the requirement using `read_file` tool.",
        "**NOTE:** Utilize 'work/' folder to execute any commands or install any packages as part of the procedure while performing the skills. Basically you need to use 'work/' as your working directory/sandbox."
    ]

    for s in skills:
        name = s.get("name", "")
        scope = s.get("scope", "project")
        path = s.get("skill_file_path", f"skills/{name}.md")
        desc = s.get("description", "")
        lines.append("---")
        lines.append(f"name: {name}")
        lines.append(f"scope: {scope}")
        lines.append(f"skill_file_path: {path}")
        lines.append(f'description: "{desc}"')

    return "\n".join(lines)

