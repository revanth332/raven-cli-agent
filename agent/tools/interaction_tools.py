import json
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger("raven.interaction_tools")

# Global handler function dispatched by RavenApp in Textual UI
_QUESTIONNAIRE_HANDLER: Optional[Callable[[str, list[dict]], dict]] = None


def set_questionnaire_handler(handler: Optional[Callable[[str, list[dict]], dict]]) -> None:
    """Registers a thread-safe callback handler for interactive questionnaires."""
    global _QUESTIONNAIRE_HANDLER
    _QUESTIONNAIRE_HANDLER = handler


def get_questionnaire_handler() -> Optional[Callable[[str, list[dict]], dict]]:
    """Returns the currently active questionnaire handler."""
    return _QUESTIONNAIRE_HANDLER


def normalize_questionnaire_payload(raw_questions: Any) -> list[dict]:
    """Defensively validates and normalizes questions payload from LLMs.
    
    Guarantees no runtime exceptions from missing keys, malformed lists,
    or unexpected formats across different LLM backends.
    """
    if not isinstance(raw_questions, list):
        if isinstance(raw_questions, dict):
            raw_questions = [raw_questions]
        else:
            raw_questions = []

    normalized = []
    # Cap batch at 4 questions to prevent cognitive and UI fatigue
    for idx, q in enumerate(raw_questions[:4]):
        if not isinstance(q, dict):
            continue

        raw_opts = q.get("options", [])
        if isinstance(raw_opts, str):
            raw_opts = [o.strip() for o in raw_opts.replace("\n", ",").split(",") if o.strip()]
        elif not isinstance(raw_opts, list):
            raw_opts = []

        opts = [str(o).strip() for o in raw_opts if str(o).strip()]
        if not opts:
            opts = ["Approve / Proceed", "Decline / Modify"]

        qid = str(q.get("id") or f"decision_{idx + 1}").strip()
        question_text = str(q.get("question") or f"Decision {idx + 1} required:").strip()
        context_text = str(q.get("context") or "").strip()

        rec = str(q.get("recommended") or "").strip()
        if not rec or rec not in opts:
            rec = opts[0]

        normalized.append({
            "id": qid,
            "question": question_text,
            "context": context_text,
            "options": opts,
            "recommended": rec
        })

    if not normalized:
        normalized.append({
            "id": "confirmation",
            "question": "Clarification required to proceed. Do you approve?",
            "context": "The agent requires explicit user confirmation before continuing.",
            "options": ["Proceed", "Abort"],
            "recommended": "Proceed"
        })

    return normalized


def ask_user(title: str, questions: list[dict]) -> dict:
    """Presents a structured, interactive questionnaire modal to the user.

    Batches up to 3-4 architectural decisions or critical confirmations,
    allowing fast keyboard selection without dumping unstructured text into chat.
    """
    safe_title = str(title).strip() if title else "User Clarification Required"
    clean_questions = normalize_questionnaire_payload(questions)

    handler = get_questionnaire_handler()
    if handler:
        try:
            return handler(safe_title, clean_questions)
        except Exception as e:
            logger.error("Questionnaire handler failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "answers": {q["id"]: q["recommended"] for q in clean_questions}
            }

    # Headless / CLI fallback if Textual UI is not active
    fallback_answers = {}
    for q in clean_questions:
        fallback_answers[q["id"]] = q["recommended"]

    return {
        "status": "completed",
        "answers": fallback_answers,
        "note": "Auto-selected recommendations (Headless environment)."
    }
