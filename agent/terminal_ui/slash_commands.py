"""
Slash commands registry and associated prompt templates for Raven CLI Agent.
"""

from typing import Any, Dict
from agent.utils import read_prompt_from_file

DEBUG_PROMPT = read_prompt_from_file("prompts/debug_prompt.md")
COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.md")
REPORT_PROMPT = read_prompt_from_file("prompts/report_prompt.md")
REVIEW_PROMPT = read_prompt_from_file("prompts/review_prompt.md")
PLAN_PROMPT = read_prompt_from_file("prompts/plan_prompt.md")
ASK_PROMPT = read_prompt_from_file("prompts/ask_prompt.md")
EXPLAIN_PROMPT = read_prompt_from_file("prompts/explain_prompt.md")

SLASH_COMMANDS: Dict[str, Dict[str, Any]] = {
    "/connect": {
        "description": "Connect to LLM provider (Base URL, API Key, Model)",
        "placeholder": "/connect",
        "system_prompt": "",
    },
    "/usage": {
        "description": "Open interactive HTML usage & token analytics dashboard",
        "placeholder": "/usage",
        "system_prompt": "",
    },
    "/exit": {
        "description": "Exit Raven CLI Agent",
        "placeholder": "/exit",
        "system_prompt": "",
    },
    "/new": {
        "description": "Start a new chat session",
        "placeholder": "/new",
        "system_prompt": "",
    },
    "/fork": {
        "description": "Fork current session state into a new conversation",
        "placeholder": "/fork [optional_title]",
        "system_prompt": "",
    },
    "/sessions": {
        "description": "List and switch chat sessions",
        "placeholder": "/sessions",
        "system_prompt": "",
    },
    "/switch": {
        "description": "Switch active chat session",
        "placeholder": "/switch",
        "system_prompt": "",
    },
    "/model": {
        "description": "Switch active AI model",
        "placeholder": "/model",
        "system_prompt": "",
    },
    "/skills": {
        "description": "View and manage installed agent skills",
        "placeholder": "/skills",
        "system_prompt": "",
    },
    "/skill": {
        "description": "Directly invoke an agent skill (/skill <name> [prompt])",
        "placeholder": "/skill <name> [prompt]",
        "system_prompt": "",
    },
    "/add-skill": {
        "description": "Create and install a new agent skill",
        "placeholder": "/add-skill",
        "system_prompt": "",
    },
    "/auto-approve": {
        "description": "Toggle Auto-Approval Mode",
        "placeholder": "/auto-approve",
        "system_prompt": "",
    },
    "/image": {
        "description": "Ask about a local image file",
        "placeholder": "/image <file_path> <query>",
        "system_prompt": "",
    },
    "/paste-image": {
        "description": "Ask about screenshot in clipboard",
        "placeholder": "/paste-image [query]",
        "system_prompt": "",
    },
    "/imagine": {
        "description": "Generate an image from prompt (/imagine <prompt>)",
        "placeholder": "/imagine <prompt>",
        "system_prompt": "",
    },
    "/image-model": {
        "description": "View or switch default image generation model (/image-model [model_name])",
        "placeholder": "/image-model [model_name]",
        "system_prompt": "",
    },
    "/compact": {
        "description": "Summarize and compact conversation history",
        "placeholder": "/compact [optional instructions]",
        "system_prompt": "",
    },
    "/checkpoint": {
        "description": "Create a transactional workspace snapshot",
        "placeholder": "/checkpoint [name]",
        "system_prompt": "",
    },
    "/rollback": {
        "description": "Roll back to previous or specified checkpoint",
        "placeholder": "/rollback [checkpoint_id]",
        "system_prompt": "",
    },
    "/checkpoints": {
        "description": "List all saved project checkpoints",
        "placeholder": "/checkpoints",
        "system_prompt": "",
    },
    "/coach": {
        "description": "Activate coach mode",
        "placeholder": "/coach",
        "system_prompt": COACH_PROMPT,
    },
    "/debug": {
        "description": "Activate debug mode",
        "placeholder": "/debug",
        "system_prompt": DEBUG_PROMPT,
    },
    "/report": {
        "description": "Generate past work report",
        "placeholder": "/report <week/month/..>",
        "system_prompt": REPORT_PROMPT,
    },
    "/plan": {
        "description": "Generate a comprehensive plan",
        "placeholder": "/plan",
        "system_prompt": PLAN_PROMPT,
    },
    "/review": {
        "description": "Generates a comprehensive code review",
        "placeholder": "/review <week/month/..>",
        "system_prompt": REVIEW_PROMPT,
    },
    "/ask": {
        "description": "Generates a architectural guidance",
        "placeholder": "/ask <week/month/..>",
        "system_prompt": ASK_PROMPT,
    },
    "/explain": {
        "description": "Generates a comprehensive explanation",
        "placeholder": "/explain <week/month/..>",
        "system_prompt": EXPLAIN_PROMPT,
    },
}


def get_dynamic_slash_commands() -> Dict[str, Dict[str, Any]]:
    """Returns static slash commands merged with dynamic skill slash commands."""
    commands = dict(SLASH_COMMANDS)
    try:
        from agent.core.skills_manager import discover_skills
        for s in discover_skills(include_disabled=False):
            name = s.get("name")
            if not name:
                continue
            cmd_key = f"/{name}"
            if cmd_key not in commands:
                desc = s.get("description", "")
                short_desc = desc[:70] + ("..." if len(desc) > 70 else "") if desc else f"Execute {name} skill"
                commands[cmd_key] = {
                    "description": f"Skill: {short_desc}",
                    "placeholder": f"/{name} [prompt]",
                    "system_prompt": "",
                    "is_skill": True,
                    "skill_name": name,
                }
    except Exception:
        pass
    return commands

