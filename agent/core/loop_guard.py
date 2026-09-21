import json
from enum import Enum
from typing import Any, Tuple, List


class LoopGuardState(str, Enum):
    CONTINUE = "continue"
    WRAP_UP = "wrap_up"
    FINALIZE = "finalize"


class LoopGuard:
    """Tracks execution budgets and detects unproductive autonomous loops."""

    def __init__(
        self,
        max_turns: int = 10,
        history_window: int = 4,
        hard_max_turns: int = 20,
        max_tool_calls: int = 40,
        max_no_progress_rounds: int = 3,
        grace_turns: int = 2,
    ):
        self.max_turns = max_turns
        self.hard_max_turns = max(hard_max_turns, max_turns)
        self.max_tool_calls = max_tool_calls
        self.max_no_progress_rounds = max_no_progress_rounds
        self.grace_turns = grace_turns
        self.history_window = history_window
        self.turn_count = 0
        self.tool_call_count = 0
        self.no_progress_rounds = 0
        self.wrap_up_started_at = None
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
        """Increments the LLM round counter and starts grace tracking at the soft limit."""
        self.turn_count += 1
        if self.turn_count >= self.max_turns and self.wrap_up_started_at is None:
            self.wrap_up_started_at = self.turn_count
        return self.turn_count

    def record_tool_call(self, count: int = 1) -> int:
        self.tool_call_count += count
        return self.tool_call_count

    def record_round_outcome(self, made_progress: bool) -> int:
        self.no_progress_rounds = 0 if made_progress else self.no_progress_rounds + 1
        return self.no_progress_rounds

    @staticmethod
    def result_made_progress(result: Any) -> bool:
        if isinstance(result, dict) and result.get("success") is False:
            return False
        normalized = str(result).strip().lower()
        return not normalized.startswith(("error", "failed", "failure"))

    def get_state(self) -> LoopGuardState:
        if (
            self.turn_count >= self.hard_max_turns
            or self.tool_call_count >= self.max_tool_calls
            or self.no_progress_rounds >= self.max_no_progress_rounds
        ):
            return LoopGuardState.FINALIZE

        if self.wrap_up_started_at is not None:
            grace_used = self.turn_count - self.wrap_up_started_at
            if grace_used >= self.grace_turns:
                return LoopGuardState.FINALIZE
            return LoopGuardState.WRAP_UP

        return LoopGuardState.CONTINUE

    def is_turn_limit_reached(self) -> bool:
        """Backward-compatible check for the hard finalization boundary."""
        return self.get_state() == LoopGuardState.FINALIZE

    def get_wrap_up_instruction(self) -> str:
        return (
            "You reached the normal autonomous execution budget. Stop broad exploration and wrap up. "
            "Use the evidence already gathered, and call another tool only when essential to verify correctness. "
            "Then provide a clear final response describing completed work, verification, and anything remaining."
        )

    def get_finalization_instruction(self) -> str:
        return (
            "The autonomous execution budget is exhausted. Do not call tools. Provide the final response now. "
            "State what was completed, what was verified, any failures or remaining work, and the recommended next action."
        )

    def get_limit_warning(self) -> str:
        return (
            "Autonomous execution budget reached; requesting a final tool-free summary "
            f"after {self.turn_count} tool rounds and {self.tool_call_count} tool calls."
        )

    def reset(self) -> None:
        """Resets the guard for a new user turn."""
        self.turn_count = 0
        self.tool_call_count = 0
        self.no_progress_rounds = 0
        self.wrap_up_started_at = None
        self.history.clear()
