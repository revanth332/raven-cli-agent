"""
Subagent Manager for Raven CLI Agent.
Manages built-in subagent presets and discovers custom Markdown subagent definitions
with YAML frontmatter across global (~/.raven/subagents) and project-local (./subagents) scopes.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.core.settings import settings
from agent.core.skills_manager import parse_frontmatter, sanitize_skill_name
from agent.utils import get_project_root, read_prompt_from_file


EXPLORE_SYSTEM_PROMPT = """You are Raven's Codebase Exploration Subagent (`explore`).
Your role is to rapidly locate files, search code patterns, read relevant sections, and return a concise, high-signal technical summary.

STRICT RULES:
1. You have read-only access to the workspace (`find_file`, `read_file`, `search_file_content`, `search_codebase`).
2. Do NOT dump entire raw files into your final response. Cite exact file paths, line numbers, function/class names, and key architectural findings.
3. Avoid redundant or duplicate tool calls. Stop exploring as soon as you have sufficient facts to answer the query accurately.
4. Keep your final response structured, direct, and compact so the parent session or user gets maximum signal with minimal token overhead."""


GIT_OPS_SYSTEM_PROMPT = """You are Raven's Git Operations Subagent (`git_ops`).
Your role is to handle git status checks, diff inspection, staging, and committing changes cleanly and autonomously.

STRICT RULES:
1. ALWAYS use `get_staged_git_changes` first to inspect staged diffs before committing. Do not read full source files.
2. If `get_staged_git_changes` reports no staged changes:
   - Call `get_git_status` to check modified/untracked files.
   - If the user explicitly asked to stage and commit (or specified files to commit), use `git_add` to stage the relevant files and then inspect `get_staged_git_changes`.
   - If the user ran `/commit` with no staged changes, inform them clearly which files are unstaged or if the working tree is clean.
3. NEVER ask the user for a commit message. Generate a concise, descriptive commit message based on the staged changes.
4. Commit messages MUST ALWAYS be strictly in **lowercase** (e.g., `feat: add subagent execution engine`).
5. Conclude with a brief confirmation stating the commit message used and the files committed."""


def _get_reporter_system_prompt() -> str:
    base_report_prompt = read_prompt_from_file("prompts/report_prompt.md")
    return (
        "You are Raven's Work Report Subagent (`reporter`).\n"
        "Your sole task is to generate a concise, professional engineering work report from git commit history.\n"
        "Use `get_current_timestamp` and `get_git_log` (with `include_stat=True`) to gather commit activity, then output the report in the exact required format.\n\n"
        f"{base_report_prompt}"
    )


GENERAL_SYSTEM_PROMPT = """You are Raven's General Worker Subagent (`general`).
You execute self-contained, multi-step engineering or research sub-tasks in an isolated context window.

STRICT RULES:
1. Complete the assigned task thoroughly using your available tools (`find_file`, `read_file`, `search_file_content`, `search_codebase`, `create_file`, `patch_file`, `execute_command`, `web_search`, `extract_content_from_web_links`).
2. Never execute the exact same tool call with identical arguments twice.
3. When modifying files, always use `patch_file` or `create_file` directly—never write temporary scripts to edit code.
4. Return a clear, concise summary of what you accomplished, any files created/modified, and key findings."""


def get_builtin_subagents() -> Dict[str, Dict[str, Any]]:
    """Returns the dictionary of built-in subagent presets."""
    return {
        "explore": {
            "name": "explore",
            "description": "Fast read-only codebase scout for finding files, grep searching, and summarizing code architecture.",
            "model": "",
            "max_steps": 12,
            "ephemeral": False,
            "allowed_tools": [
                "find_file",
                "read_file",
                "search_file_content",
                "search_codebase",
            ],
            "system_prompt": EXPLORE_SYSTEM_PROMPT,
            "scope": "builtin",
        },
        "git_ops": {
            "name": "git_ops",
            "description": "Git specialist for inspecting diffs/status, staging files, and committing with lowercase messages (powers /commit).",
            "model": "",
            "max_steps": 8,
            "ephemeral": False,
            "allowed_tools": [
                "get_git_status",
                "get_staged_git_changes",
                "get_git_diff",
                "get_git_log",
                "git_add",
                "commit_staged_git_changes",
            ],
            "system_prompt": GIT_OPS_SYSTEM_PROMPT,
            "scope": "builtin",
        },
        "reporter": {
            "name": "reporter",
            "description": "Work and standup report generator from git commit logs and file stats (powers /report).",
            "model": "",
            "max_steps": 6,
            "ephemeral": True,
            "allowed_tools": [
                "get_current_timestamp",
                "get_git_log",
            ],
            "system_prompt": _get_reporter_system_prompt(),
            "scope": "builtin",
        },
        "general": {
            "name": "general",
            "description": "General-purpose isolated worker for multi-step coding, file editing, command execution, or web research sub-tasks.",
            "model": "",
            "max_steps": 15,
            "ephemeral": False,
            "allowed_tools": [
                "find_file",
                "read_file",
                "search_file_content",
                "search_codebase",
                "create_file",
                "patch_file",
                "execute_command",
                "web_search",
                "extract_content_from_web_links",
                "get_current_timestamp",
            ],
            "system_prompt": GENERAL_SYSTEM_PROMPT,
            "scope": "builtin",
        },
    }


def get_global_subagents_dir() -> Path:
    """Returns the user's global subagents directory (~/.raven/subagents)."""
    d = Path.home() / ".raven" / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_project_subagents_dir() -> Path:
    """Returns the project-local subagents directory (<project_root>/subagents) without auto-creating unless needed."""
    return get_project_root() / "subagents"


def _load_subagent_from_markdown(md_path: Path, scope: str) -> Optional[Dict[str, Any]]:
    """Parses a Markdown file with YAML frontmatter into a subagent definition dict."""
    try:
        raw_text = md_path.read_text(encoding="utf-8")
    except Exception:
        return None

    meta, body = parse_frontmatter(raw_text)
    raw_name = str(meta.get("name") or md_path.stem).strip()
    name = sanitize_skill_name(raw_name)
    if not name:
        return None

    description = str(meta.get("description") or f"Custom subagent '{name}'").strip()
    model = str(meta.get("model") or "").strip()

    try:
        max_steps = int(meta.get("max_steps", 12))
    except (ValueError, TypeError):
        max_steps = 12
    max_steps = max(1, min(max_steps, 40))

    ephemeral_val = meta.get("ephemeral", False)
    if isinstance(ephemeral_val, str):
        ephemeral = ephemeral_val.strip().lower() in ("true", "1", "yes")
    else:
        ephemeral = bool(ephemeral_val)

    allowed_tools_raw = meta.get("allowed_tools", [])
    if isinstance(allowed_tools_raw, str):
        allowed_tools = [t.strip() for t in allowed_tools_raw.split(",") if t.strip()]
    elif isinstance(allowed_tools_raw, list):
        allowed_tools = [str(t).strip() for t in allowed_tools_raw if str(t).strip()]
    else:
        allowed_tools = []

    system_prompt = body.strip()
    if not system_prompt:
        system_prompt = f"You are the '{name}' subagent. {description}"

    return {
        "name": name,
        "description": description,
        "model": model,
        "max_steps": max_steps,
        "ephemeral": ephemeral,
        "allowed_tools": allowed_tools,
        "system_prompt": system_prompt,
        "scope": scope,
        "file_path": str(md_path),
    }


def discover_subagents() -> List[Dict[str, Any]]:
    """
    Discovers all available subagents across Built-in, Global (~/.raven/subagents),
    and Project-local (./subagents) scopes.
    Precedence: Project-local > Global > Built-in.
    """
    registry: Dict[str, Dict[str, Any]] = get_builtin_subagents()

    # 1. Global custom subagents
    global_dir = get_global_subagents_dir()
    if global_dir.exists() and global_dir.is_dir():
        for md_file in sorted(global_dir.glob("*.md")):
            parsed = _load_subagent_from_markdown(md_file, scope="global")
            if parsed:
                registry[parsed["name"]] = parsed

    # 2. Project-local custom subagents
    project_dir = get_project_subagents_dir()
    if project_dir.exists() and project_dir.is_dir():
        for md_file in sorted(project_dir.glob("*.md")):
            parsed = _load_subagent_from_markdown(md_file, scope="project")
            if parsed:
                registry[parsed["name"]] = parsed

    return list(registry.values())


def get_subagent(name: str) -> Optional[Dict[str, Any]]:
    """Retrieves a specific subagent definition by name (case-insensitive)."""
    if not name:
        return None
    clean_name = sanitize_skill_name(name)
    for sub in discover_subagents():
        if sub["name"] == clean_name or sub["name"] == name.strip().lower():
            return sub
    return None


def resolve_subagent_model(subagent: Dict[str, Any], fallback_model: Optional[str] = None) -> str:
    """
    Resolves the model to use for a subagent following the hierarchy:
    1. Explicit `model` in subagent definition
    2. settings.RAVEN_SMALL_MODEL (configured cheap/fast model)
    3. fallback_model or settings.RAVEN_MODEL (active primary model)
    """
    explicit_model = str(subagent.get("model") or "").strip()
    if explicit_model and explicit_model.lower() not in ("none", "null", "auto"):
        return explicit_model

    small_model = getattr(settings, "RAVEN_SMALL_MODEL", None) or getattr(settings, "SMALL_MODEL", None)
    if small_model and str(small_model).strip():
        return str(small_model).strip()

    primary_model = fallback_model or getattr(settings, "RAVEN_MODEL", None) or getattr(settings, "MODEL", None)
    return str(primary_model or "google/gemini-3-flash-preview").strip()


def detect_git_author() -> str:
    """Auto-detects the current repository's git author name without requiring an LLM tool call."""
    try:
        res = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%an"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    return ""


def build_subagents_prompt_section() -> str:
    """Builds the SUBAGENTS section injected into the primary agent's system prompt."""
    subagents = discover_subagents()
    if not subagents:
        return ""

    lines = [
        "You can delegate self-contained or context-heavy tasks to specialized isolated subagents using the `delegate_to_subagent` tool.",
        "Subagents run in an isolated context window on a fast/cost-effective model and return only their concise final summary to you.",
        "WHEN TO USE SUBAGENTS:",
        "- Use `explore` when you need to search across multiple files or scout unfamiliar parts of the codebase without polluting your main context window with raw file reads.",
        "- Use `git_ops` when the user asks you to stage and/or commit changes.",
        "- Use `reporter` when the user asks for a work/standup summary of recent git commits.",
        "- Use `general` for isolated multi-step subtasks that do not require the full conversation history.",
        "",
        "AVAILABLE SUBAGENTS:",
    ]
    for sub in subagents:
        tools_str = ", ".join(sub.get("allowed_tools", [])) or "none"
        lines.append(
            f"- `{sub['name']}` ({sub.get('scope', 'builtin')}): {sub['description']} [Tools: {tools_str}]"
        )
    return "\n".join(lines)
