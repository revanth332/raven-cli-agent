import json
import os
import time
from pathlib import Path
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea
from textual import events
from agent.tools.file_tools import is_sensitive_file


MAX_INPUT_HISTORY = 10
INPUT_HISTORY_FILE = Path.home() / ".raven" / "input_history.json"

PASTE_COLLAPSE_MIN_LINES = 5
PASTE_COLLAPSE_MIN_CHARS = 300

_WORKSPACE_FILES_CACHE: list[str] = []
_WORKSPACE_FILES_CACHE_TS: float = 0.0
_WORKSPACE_FILES_CACHE_ROOT: str = ""
_WORKSPACE_IGNORE_DIRS = {
    "node_modules", ".git", "venv", ".env", ".venv", "env", "__pycache__",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".turbo", ".next", ".nuxt", ".cache", ".idea", ".vscode", ".vs",
    ".coverage", "htmlcov",
}
_WORKSPACE_IGNORE_EXTS = {".pyc", ".pyo", ".pyd"}

EXCLUDED_HISTORY_COMMANDS = {
    "exit",
    "quit",
    "/exit",
    "/sessions",
    "/connect",
    "/usage",
    "/new",
    "/editor",
    "/fork",
    "/export",
    "/model",
    "/models",
    "/skills",
    "/subagents",
    "/checkpoints",
    "/auto-approve",
    "/image-model",
}

COMMANDS_REQUIRING_ARGS = {
    "/image",
    "/imagine",
    "/skill",
    "/subagent",
}


def get_workspace_files(ttl: float = 5.0, max_scan: int = 5000) -> list[str]:
    """Returns a cached list of non-ignored, non-sensitive relative workspace file paths."""
    global _WORKSPACE_FILES_CACHE, _WORKSPACE_FILES_CACHE_TS, _WORKSPACE_FILES_CACHE_ROOT
    now = time.monotonic()
    cwd = os.getcwd()
    if _WORKSPACE_FILES_CACHE and _WORKSPACE_FILES_CACHE_ROOT == cwd and (now - _WORKSPACE_FILES_CACHE_TS) < ttl:
        return _WORKSPACE_FILES_CACHE

    collected: list[str] = []
    try:
        for root, dirs, files in os.walk("."):
            dirs[:] = [
                d for d in dirs
                if d not in _WORKSPACE_IGNORE_DIRS
                and not d.endswith(".egg-info")
                and not (("venv" in d.lower() or d.lower() == "env") and (Path(root) / d / "pyvenv.cfg").exists())
            ]
            for file in files:
                f_lower = file.lower()
                if any(f_lower.endswith(ext) for ext in _WORKSPACE_IGNORE_EXTS):
                    continue
                try:
                    rel_path = Path(os.path.join(root, file)).relative_to(".").as_posix()
                except ValueError:
                    rel_path = (Path(root) / file).as_posix().lstrip("./")
                if is_sensitive_file(rel_path):
                    continue
                collected.append(rel_path)
                if len(collected) >= max_scan:
                    break
            if len(collected) >= max_scan:
                break
    except Exception:
        pass

    collected.sort(key=lambda p: (p.count("/"), p.lower()))
    _WORKSPACE_FILES_CACHE = collected
    _WORKSPACE_FILES_CACHE_TS = now
    _WORKSPACE_FILES_CACHE_ROOT = cwd
    return collected


def _subsequence_span(needle: str, haystack: str) -> int | None:
    """Returns the span length if all chars of needle appear in order in haystack, else None."""
    if not needle:
        return 0
    first_idx = -1
    cur = 0
    for ch in needle:
        pos = haystack.find(ch, cur)
        if pos == -1:
            return None
        if first_idx == -1:
            first_idx = pos
        cur = pos + 1
    return cur - first_idx


def fuzzy_search_workspace_files(query: str, max_results: int = 15) -> list[str]:
    """Fuzzy-searches workspace files for '@' reference autocomplete."""
    files = get_workspace_files()
    q = query.strip().replace("\\", "/").lstrip("./").lower()
    if not q:
        return files[:max_results]

    scored: list[tuple[tuple, str]] = []
    for rel_path in files:
        rel_lower = rel_path.lower()
        fname_lower = rel_lower.rsplit("/", 1)[-1]

        if fname_lower == q:
            rank = (0, len(rel_path), rel_lower)
        elif rel_lower == q:
            rank = (1, len(rel_path), rel_lower)
        elif fname_lower.startswith(q):
            rank = (2, len(fname_lower), len(rel_path), rel_lower)
        elif rel_lower.startswith(q) or f"/{q}" in rel_lower:
            rank = (3, len(rel_path), rel_lower)
        elif q in fname_lower:
            rank = (4, fname_lower.find(q), len(fname_lower), len(rel_path), rel_lower)
        elif q in rel_lower:
            rank = (5, rel_lower.find(q), len(rel_path), rel_lower)
        else:
            f_span = _subsequence_span(q, fname_lower)
            if f_span is not None:
                rank = (6, f_span, len(fname_lower), len(rel_path), rel_lower)
            else:
                p_span = _subsequence_span(q, rel_lower)
                if p_span is not None:
                    rank = (7, p_span, len(rel_path), rel_lower)
                else:
                    continue

        scored.append((rank, rel_path))

    scored.sort(key=lambda item: item[0])
    return [path for _, path in scored[:max_results]]


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
        Binding("ctrl+p", "toggle_paste_summary", "Toggle Paste Summary", priority=True),
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
        self._pasted_blocks: dict[str, str] = {}
        self._paste_counter: int = 0
        self._paste_collapsed: bool = True

    def register_pasted_block(self, raw_text: str) -> str:
        """Registers a large pasted block and returns its compact placeholder token."""
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        line_count = len(lines)
        char_count = len(normalized)
        self._paste_counter += 1
        if line_count >= PASTE_COLLAPSE_MIN_LINES:
            token = f"[Pasted #{self._paste_counter}: {line_count} lines]"
        elif line_count > 1:
            token = f"[Pasted #{self._paste_counter}: {char_count} chars ({line_count} lines)]"
        else:
            token = f"[Pasted #{self._paste_counter}: {char_count} chars]"
        self._pasted_blocks[token] = normalized
        self._paste_collapsed = True
        return token

    def get_expanded_text(self) -> str:
        """Returns the input text with all collapsed paste summary tokens expanded."""
        result = self.text
        if not self._pasted_blocks:
            return result
        for token, content in self._pasted_blocks.items():
            if token in result:
                result = result.replace(token, content)
        return result

    def clear_pasted_blocks(self) -> None:
        """Clears stored paste blocks and resets the paste counter."""
        self._pasted_blocks.clear()
        self._paste_counter = 0
        self._paste_collapsed = True

    def action_toggle_paste_summary(self) -> None:
        """Toggles between collapsed [Pasted #N: X lines] tokens and full pasted text."""
        if not self._pasted_blocks:
            return

        current = self.text
        has_collapsed_token = any(token in current for token in self._pasted_blocks)

        if has_collapsed_token:
            for token, content in self._pasted_blocks.items():
                if token in current:
                    current = current.replace(token, content)
            self._paste_collapsed = False
            self._suppress_autocomplete_once = True
            self.text = current
            lines = current.split("\n") if current else [""]
            self.cursor_location = (max(0, len(lines) - 1), len(lines[-1]))
        else:
            has_expanded = any(content in current for content in self._pasted_blocks.values())
            if has_expanded:
                for token, content in sorted(self._pasted_blocks.items(), key=lambda x: len(x[1]), reverse=True):
                    if content in current:
                        current = current.replace(content, token)
                self._paste_collapsed = True
                self._suppress_autocomplete_once = True
                self.text = current
                lines = current.split("\n") if current else [""]
                self.cursor_location = (max(0, len(lines) - 1), len(lines[-1]))

    def _on_paste(self, event: events.Paste) -> None:
        """Intercepts multi-line or large pastes and collapses them into summary tokens."""
        if self.read_only:
            event.stop()
            return

        raw_text = event.text or ""
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        line_count = len(normalized.split("\n"))
        char_count = len(normalized)

        if line_count >= PASTE_COLLAPSE_MIN_LINES or char_count >= PASTE_COLLAPSE_MIN_CHARS:
            token = self.register_pasted_block(normalized)
            self._navigating_history = False
            self._suppress_autocomplete_once = True
            self.replace(token, *self.selection, maintain_selection_offset=False)
            event.stop()
            event.prevent_default()
            try:
                self.app.notify(
                    f"Collapsed {line_count} lines (Ctrl+P to expand/collapse)",
                    timeout=2.2,
                )
            except Exception:
                pass
            return

        super()._on_paste(event)

    def get_active_at_mention(self) -> tuple[str, tuple[int, int], tuple[int, int]] | None:
        """Detects an active '@file' reference query at the current cursor position.

        Returns:
            Tuple of (query_string, start_location, end_location) if an active '@'
            token is under the cursor, otherwise None.
        """
        raw = self.text
        if not raw or "@" not in raw:
            return None

        lines = raw.split("\n")
        row, col = self.cursor_location
        if row < 0 or row >= len(lines):
            return None

        line = lines[row]
        col = max(0, min(col, len(line)))
        prefix = line[:col]
        at_idx = prefix.rfind("@")
        if at_idx == -1:
            return None

        # Ensure '@' is at start of line or preceded by whitespace/opening punctuation (not an email)
        if at_idx > 0 and prefix[at_idx - 1] not in (" ", "\t", "(", "[", "{", "\"", "'", ","):
            return None

        query_part = prefix[at_idx + 1:]
        if " " in query_part or "\t" in query_part:
            return None

        return (query_part, (row, at_idx), (row, col))

    def complete_at_mention(self, selected_path: str) -> bool:
        """Replaces the active '@query' token under the cursor with '@<selected_path> '."""
        mention = self.get_active_at_mention()
        if mention is None:
            return False
        _, start_loc, end_loc = mention
        replacement = f"@{selected_path} "
        self._suppress_autocomplete_once = True
        self._navigating_history = False
        self.replace(replacement, start_loc, end_loc, maintain_selection_offset=False)
        return True

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

    def action_copy(self) -> None:
        """Copy selected text from the input box or screen to the system clipboard."""
        from agent.terminal_ui.chat_message import copy_to_system_clipboard

        selected = self.selected_text
        if not selected:
            try:
                selected = self.screen.get_selected_text() or ""
            except Exception:
                selected = ""

        if selected:
            copy_to_system_clipboard(selected, app=self.app)
            self.app.notify("✓ Copied to clipboard", timeout=1.8)

    def action_submit(self) -> None:
        try:
            autocomplete = self.app.query_one("#autocomplete_list")
            if autocomplete.styles.display == "block":
                if hasattr(self.app, "select_autocomplete_option"):
                    self.app.select_autocomplete_option()
                return
        except Exception:
            pass
        expanded_text = self.get_expanded_text()
        self.post_message(self.Submitted(self, expanded_text))

    def action_newline(self) -> None:
        self._navigating_history = False
        self._suppress_autocomplete_once = False
        self.insert("\n")