import json
from pathlib import Path
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea
from textual import events


MAX_INPUT_HISTORY = 10
INPUT_HISTORY_FILE = Path.home() / ".raven" / "input_history.json"

EXCLUDED_HISTORY_COMMANDS = {
    "exit",
    "quit",
    "/exit",
    "/sessions",
    "/connect",
    "/usage",
    "/new",
    "/fork",
    "/model",
    "/models",
    "/skills",
    "/checkpoints",
    "/auto-approve",
    "/image-model",
}

COMMANDS_REQUIRING_ARGS = {
    "/image",
    "/imagine",
    "/skill",
}


def should_record_query(raw_query: str) -> bool:
    """Returns True if the submitted query should be stored in input history."""
    stripped = raw_query.strip()
    if not stripped:
        return False

    parts = stripped.split()
    first_token = parts[0].lower()

    if first_token in EXCLUDED_HISTORY_COMMANDS:
        return False

    if first_token in COMMANDS_REQUIRING_ARGS and len(parts) < 2:
        return False

    return True


class ChatInput(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("shift+enter", "newline", "Newline", priority=True),
        Binding("shift+return", "newline", "Newline", priority=True),
        Binding("alt+enter", "newline", "Newline", priority=True),
        Binding("ctrl+j", "newline", "Newline", priority=True),
    ]

    class Submitted(Message):
        def __init__(self, text_area: "ChatInput", value: str) -> None:
            self.text_area = text_area
            self.value = value
            super().__init__()

    def __init__(
        self,
        *args,
        history_file: Path | None = None,
        **kwargs,
    ) -> None:
        """Initializes the ChatInput widget.

        Args:
            *args: Positional arguments forwarded to TextArea.
            history_file: Optional custom file path for storing input history.
                Provided for deterministic testing and isolation without mutating
                the user's global history file.
            **kwargs: Keyword arguments forwarded to TextArea.
        """
        super().__init__(*args, **kwargs)
        self.input_history_file: Path = history_file or INPUT_HISTORY_FILE
        self.input_history: list[str] = self.load_input_history()
        self.input_history_index: int | None = None
        self._draft_text: str = ""
        self._navigating_history: bool = False
        self._suppress_autocomplete_once: bool = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Exits rapid history-cycling mode when the user clicks to place the cursor."""
        self._navigating_history = False
        self._suppress_autocomplete_once = False

    def load_input_history(self) -> list[str]:
        """Loads up to MAX_INPUT_HISTORY queries from disk."""
        try:
            if self.input_history_file.exists():
                data = json.loads(self.input_history_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    valid = [str(item) for item in data if isinstance(item, str) and item.strip()]
                    return valid[-MAX_INPUT_HISTORY:]
        except Exception:
            pass
        return []

    def save_input_history(self) -> None:
        """Persists the current input history list to disk."""
        try:
            self.input_history_file.parent.mkdir(parents=True, exist_ok=True)
            self.input_history_file.write_text(
                json.dumps(self.input_history[-MAX_INPUT_HISTORY:], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def reset_history_navigation(self) -> None:
        """Resets history browsing state and stashed draft."""
        self.input_history_index = None
        self._draft_text = ""
        self._navigating_history = False
        self._suppress_autocomplete_once = False

    def add_to_history(self, query: str) -> None:
        """Records a submitted user query into history with MRU deduplication."""
        self.reset_history_navigation()
        cleaned = query.strip()
        if not should_record_query(cleaned):
            return

        # Deduplicate while preserving Most-Recently-Used order
        self.input_history = [item for item in self.input_history if item != cleaned]
        self.input_history.append(cleaned)
        if len(self.input_history) > MAX_INPUT_HISTORY:
            self.input_history = self.input_history[-MAX_INPUT_HISTORY:]
        self.save_input_history()

    def add_to_input_history(self, query: str) -> None:
        """Alias for add_to_history."""
        self.add_to_history(query)

    def _set_recalled_text(self, new_text: str, navigating: bool = True) -> None:
        """Updates the input box text from history and positions cursor at the end."""
        self._suppress_autocomplete_once = True
        self._navigating_history = navigating
        self.text = new_text
        lines = new_text.split("\n") if new_text else [""]
        last_row = max(0, len(lines) - 1)
        last_col = len(lines[-1])
        self.cursor_location = (last_row, last_col)

    def navigate_history_up(self) -> bool:
        """Moves backward (older) in input history. Returns True if handled."""
        if not self.input_history:
            return False

        if self.input_history_index is None:
            self._draft_text = self.text
            self.input_history_index = len(self.input_history) - 1
        elif self.input_history_index > 0:
            self.input_history_index -= 1
        else:
            # Already at the oldest history item; keep cursor at end and consume key
            self._navigating_history = True
            return True

        self._set_recalled_text(self.input_history[self.input_history_index], navigating=True)
        return True

    def navigate_history_down(self) -> bool:
        """Moves forward (newer) in input history or restores draft. Returns True if handled."""
        if self.input_history_index is None:
            return False

        if self.input_history_index < len(self.input_history) - 1:
            self.input_history_index += 1
            self._set_recalled_text(self.input_history[self.input_history_index], navigating=True)
        else:
            draft = self._draft_text
            self.input_history_index = None
            self._draft_text = ""
            self._set_recalled_text(draft, navigating=False)
        return True

    def _is_autocomplete_open(self) -> bool:
        """Returns True if the slash-command autocomplete dropdown is currently visible."""
        try:
            autocomplete = self.app.query_one("#autocomplete_list")
            return autocomplete.styles.display == "block"
        except Exception:
            return False

    def on_key(self, event: events.Key) -> None:
        if event.key in ("shift+enter", "shift+return", "alt+enter", "ctrl+j", "ctrl+enter") or (
            event.key in ("enter", "return") and ("shift" in event.modifiers or "alt" in event.modifiers or "ctrl" in event.modifiers)
        ):
            self._navigating_history = False
            self._suppress_autocomplete_once = False
            self.insert("\n")
            event.prevent_default()
            event.stop()
            return

        if event.key in ("enter", "return") and self.text.endswith("\\"):
            self._navigating_history = False
            self._suppress_autocomplete_once = False
            self.text = self.text[:-1]
            self.insert("\n")
            event.prevent_default()
            event.stop()
            return

        # Yield arrow navigation when slash-command autocomplete dropdown is open
        if self._is_autocomplete_open() and event.key in ("up", "down", "tab", "enter"):
            super()._on_key(event)
            return

        # Arrow navigation for in-stream decision cards when input is empty
        if getattr(self.app, "pending_questionnaire", False) and not self.text.strip():
            if event.key in ("left", "up"):
                try:
                    bar = self.app.query_one("#questionnaire_bar")
                    if hasattr(bar, "select_previous"):
                        bar.select_previous()
                        event.prevent_default()
                        event.stop()
                        return
                except Exception:
                    pass
            elif event.key in ("right", "down"):
                try:
                    bar = self.app.query_one("#questionnaire_bar")
                    if hasattr(bar, "select_next"):
                        bar.select_next()
                        event.prevent_default()
                        event.stop()
                        return
                except Exception:
                    pass

        # Input history navigation when no permission/questionnaire overlay is blocking
        if not getattr(self.app, "pending_permission", False) and not getattr(self.app, "pending_questionnaire", False):
            if event.key == "up":
                if self._navigating_history or self.cursor_location[0] == 0:
                    if self.navigate_history_up():
                        event.prevent_default()
                        event.stop()
                        return
            elif event.key == "down":
                last_row = max(0, len(self.text.split("\n")) - 1)
                if self.input_history_index is not None and (
                    self._navigating_history or self.cursor_location[0] >= last_row
                ):
                    if self.navigate_history_down():
                        event.prevent_default()
                        event.stop()
                        return
            else:
                self._navigating_history = False
                self._suppress_autocomplete_once = False

        super()._on_key(event)

    def action_submit(self) -> None:
        try:
            autocomplete = self.app.query_one("#autocomplete_list")
            if autocomplete.styles.display == "block":
                if hasattr(self.app, "select_autocomplete_option"):
                    self.app.select_autocomplete_option()
                return
        except Exception:
            pass
        self.post_message(self.Submitted(self, self.text))

    def action_newline(self) -> None:
        self._navigating_history = False
        self._suppress_autocomplete_once = False
        self.insert("\n")