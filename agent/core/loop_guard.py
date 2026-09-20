import json
from typing import Dict, Any, Tuple, List, Optional


class LoopGuard:
    """
    Safeguards agent execution loops against infinite tool repetitions,
    duplicate parameter calls, and unbounded autonomous turns.
    """

    def __init__(self, max_turns: int = 10, history_window: int = 4):
        self.max_turns = max_turns
        self.history_window = history_window
        self.turn_count = 0
        # List of canonical tool call signatures: (tool_name, normalized_args_json)
        self.history: List[Tuple[str, str]] = []

    def _normalize_args(self, args: Any) -> str:
        """Converts args dictionary or string into a canonical JSON representation."""
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                return args.strip()
        if isinstance(args, dict):
            try:
                return json.dumps(args, sort_keys=True)
            except Exception:
                return str(args)
        return str(args)

    def check_duplicate(self, tool_name: str, tool_args: Any) -> Tuple[bool, str]:
        """
        Checks whether this exact tool call with identical parameters
        has already been executed within the recent sliding window.
        """
        canonical_args = self._normalize_args(tool_args)
        signature = (tool_name, canonical_args)

        # Look in recent call history
        if signature in self.history[-self.history_window:]:
            warning_msg = (
                f"Warning: Duplicate tool call intercepted. You already executed '{tool_name}' "
                f"with these exact arguments in a previous turn. Do NOT call '{tool_name}' again "
                f"with the same arguments. Formulate your final response with what you already gathered "
                f"or inspect a different target."
            )
            return True, warning_msg

        return False, ""

    def record_call(self, tool_name: str, tool_args: Any) -> None:
        """Records a tool call into the history window."""
        canonical_args = self._normalize_args(tool_args)
        self.history.append((tool_name, canonical_args))
        if len(self.history) > self.history_window * 3:
            self.history = self.history[-self.history_window * 2:]

    def increment_turn(self) -> int:
        """Increments the autonomous turn counter."""
        self.turn_count += 1
        return self.turn_count

    def is_turn_limit_reached(self) -> bool:
        """Checks if the autonomous loop turn ceiling has been reached."""
        return self.turn_count >= self.max_turns

    def get_limit_warning(self) -> str:
        """Returns notification message when turn limit is reached."""
        return (
            f"Autonomous execution stopped: reached maximum of {self.max_turns} consecutive tool turns. "
            f"Please summarize your current progress and findings to the user."
        )

    def reset(self) -> None:
        """Resets the guard for a new user turn."""
        self.turn_count = 0
        self.history.clear()
