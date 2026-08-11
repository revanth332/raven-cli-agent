"""
Session management module for persisting and switching conversation sessions.
Sessions are stored as JSON files in ~/.raven/sessions/<session_id>.json.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from threading import Lock

_session_lock = Lock()


def get_sessions_dir() -> Path:
    """
    Returns Path to ~/.raven/sessions/ directory, creating it if necessary.
    """
    sessions_dir = Path.home() / ".raven" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def create_session(model_name: str = "gpt-4o", session_id: Optional[str] = None, title: str = "New Conversation") -> Dict[str, Any]:
    """
    Creates a new session dictionary and persists it to disk.
    """
    if not session_id:
        session_id = str(uuid.uuid4())[:8]

    now_iso = datetime.now(timezone.utc).isoformat()
    session_data = {
        "session_id": session_id,
        "title": title,
        "created_at": now_iso,
        "updated_at": now_iso,
        "model_name": model_name,
        "messages": []
    }
    save_session(session_data)
    set_active_session_id(session_id)
    return session_data


def save_session(session_data: Dict[str, Any]) -> None:
    """
    Saves or updates a session JSON file atomically.
    """
    session_id = session_data.get("session_id")
    if not session_id:
        return

    session_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    sessions_dir = get_sessions_dir()
    file_path = sessions_dir / f"{session_id}.json"
    temp_path = sessions_dir / f"{session_id}.tmp"

    with _session_lock:
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            temp_path.replace(file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)


def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Loads session data dictionary for the given session_id.
    """
    if not session_id:
        return None

    file_path = get_sessions_dir() / f"{session_id}.json"
    if not file_path.exists():
        return None

    with _session_lock:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


def list_sessions() -> List[Dict[str, Any]]:
    """
    Lists metadata summaries of all sessions, sorted by updated_at descending.
    """
    sessions_dir = get_sessions_dir()
    summaries = []

    for file_path in sessions_dir.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                summaries.append({
                    "session_id": data.get("session_id", file_path.stem),
                    "title": data.get("title", "Untitled Conversation"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "model_name": data.get("model_name", "gpt-4o"),
                    "message_count": len(data.get("messages", [])),
                })
        except Exception:
            continue

    summaries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return summaries


def delete_session(session_id: str) -> bool:
    """
    Deletes a session file from disk.
    """
    file_path = get_sessions_dir() / f"{session_id}.json"
    with _session_lock:
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception:
                return False
    return False


def get_active_session_id() -> Optional[str]:
    """
    Reads active_session.txt to determine current session ID.
    """
    active_file = get_sessions_dir().parent / "active_session.txt"
    if active_file.exists():
        try:
            return active_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


def set_active_session_id(session_id: str) -> None:
    """
    Persists current active session ID to active_session.txt.
    """
    active_file = get_sessions_dir().parent / "active_session.txt"
    try:
        active_file.write_text(session_id, encoding="utf-8")
    except Exception:
        pass
