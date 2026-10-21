# In-App Mouse Text Selection & Auto-Copy Specification (OpenCode-Style)

## 1. Problem Statement & Root Cause Analysis

Currently, users cannot highlight and copy text via mouse click-and-drag inside Raven's TUI responses, and clicking the message "Copy" button can silently fail on Windows.

### Why Click-and-Drag Selection Fails Today
1. **Terminal Mouse Capture:** Raven runs in a full-screen Textual alternate screen buffer with mouse tracking enabled. All mouse click, drag, and release events are intercepted by the TUI rather than the host terminal emulator.
2. **Textual 8.2.8 Selection Engine Limitation with `RichVisual`:**
   - Textual 8.2.8 includes a built-in screen-level mouse selection engine (`Screen._select_state`, `Screen.selections`, `Compositor.get_widget_and_offset_at`, and `events.TextSelected`).
   - However, Textual's selection engine **only** works out-of-the-box for widgets whose `_render()` returns `textual.content.Content` or `rich.text.Text`.
   - Raven renders assistant responses, code blocks, diffs, and tool outputs by passing Rich renderables (`rich.markdown.Markdown`, `rich.syntax.Syntax`, `rich.console.Group`, `rich.table.Table`) into `Static` widgets.
   - Textual wraps these Rich renderables inside `textual.visual.RichVisual`:
     - `RichVisual.render_strips()` does **not** attach character offset metadata (`meta={"offset": (char_x, line_y)}`) to rendered `Segment`s, so `Compositor.get_widget_and_offset_at(x, y)` returns `offset = None` when clicking or dragging over a response.
     - `RichVisual.render_strips()` ignores `options.selection` and `options.selection_style`, so no visual highlight is painted during mouse drag.
     - `Static.get_selection(selection)` checks `if isinstance(visual, (Text, Content)):` and returns `None` for `RichVisual`, preventing `Screen.get_selected_text()` from extracting any text.

### Why Clipboard Copy Fails Silently on Windows
1. `RavenApp._copy_to_clipboard()` calls `self.copy_to_clipboard(text)` (which emits an OSC 52 escape sequence that many Windows terminal configurations ignore) and falls back to `import pyperclip` inside a `try...except Exception: pass` block.
2. Because `pyperclip` is not declared in `pyproject.toml`, the fallback raises `ImportError`, gets swallowed silently, and still displays the `"✓ Copied Text!"` notification even though the OS clipboard was never updated.

---

## 2. Design Goals

1. **Universal In-App Mouse Drag Selection:** Enable native click-and-drag text highlighting across all assistant responses, user query cards, markdown blocks, syntax-highlighted diffs, and tool output panels without breaking streaming performance or existing `RAVEN_MARKDOWN_THEME` styling.
2. **Visual Selection Highlighting:** Render a high-contrast selection highlight (`screen--selection` / `options.selection_style`) across any `RichVisual` or `Content` widget in real time as the user drags the mouse.
3. **OpenCode-Style Auto-Copy on Mouse Release:** Automatically copy the highlighted text to the system clipboard as soon as the user releases the mouse button (`events.TextSelected`), display a concise toast notification, and support `Ctrl+C` as well.
4. **Zero-Dependency Native System Clipboard:** Implement a reliable cross-platform clipboard utility (`win32` `ctypes` / `clip` on Windows, `pbcopy` on macOS, `xclip`/`xsel`/`wl-copy` on Linux, plus Textual's OSC 52 `app.copy_to_clipboard`) so both drag-selection and the message "Copy" button work 100% of the time.

---

## 3. Technical Architecture

### 3.1 Enhancing `RichVisual` & `Static` for Selection (`agent/terminal_ui/selectable_rich.py` or `chat_message.py`)

Instead of replacing `rich.markdown.Markdown` with DOM-heavy `textual.widgets.Markdown` (which breaks synchronous streaming updates, custom `Group`/`Syntax` renderables, and theme overrides), we bridge `RichVisual` into Textual's native coordinate-offset and selection pipeline:

1. **Offset Metadata Injection & Highlight Splitting in `RichVisual.render_strips`:**
   - After `console.render_lines(...)` produces `line_segments: list[list[Segment]]` for width `width`:
   - For each line index `y` and its segments:
     - Walk each `Segment(text, style, control)`. Ignore control segments.
     - Track the character offset `char_x` along line `y`.
     - Attach `{"offset": (char_x, y)}` metadata to each segment's `rich.style.Style` so `Compositor.get_widget_and_offset_at(x, y)` resolves the exact `(char_x, y)` coordinate under the mouse cursor.
     - Check `options.selection.get_span(y)` when `options.selection` and `options.selection_style` are present:
       - If the active selection span `[sel_start, sel_end)` overlaps `[char_x, char_x + len(text))` (or `sel_end == -1` for end-of-line), split the segment into up to 3 sub-segments (before selection, selected slice with `style + selection_rich_style` and updated `offset` metadata, after selection).
   - Cache the rendered plain text (`"\n".join(line_texts)`) on the `RichVisual` instance (`self._rendered_plain_text`).

2. **Selection Extraction in `Static.get_selection`:**
   - Extend `Static.get_selection(self, selection: Selection) -> tuple[str, str] | None`:
     - If `visual` is `Text` or `Content`, extract from `str(visual)`.
     - If `visual` is `RichVisual` and has `_rendered_plain_text`, extract via `selection.extract(visual._rendered_plain_text), "\n"`.

### 3.2 OpenCode-Style Auto-Copy on `events.TextSelected` (`agent/terminal_ui/app.py`)

1. Handle `on_text_selected(self, event: events.TextSelected) -> None` in `RavenApp`:
   - Query `selected_text = self.screen.get_selected_text()`.
   - If `selected_text` is non-empty:
     - Copy `selected_text` to the system clipboard via `_copy_to_clipboard(selected_text)`.
     - Trigger a subtle toast notification (`"✓ Copied to clipboard"`).
     - Optionally clear or retain visual selection until the next click (Textual automatically clears selection when clicking elsewhere or pressing `Escape`).

### 3.3 Reliable Native Clipboard Engine (`agent/terminal_ui/app.py`)

Replace the fragile `pyperclip` fallback in `RavenApp._copy_to_clipboard(text: str)` with a multi-layered clipboard writer:
1. **OSC 52:** Call `self.copy_to_clipboard(text)` for remote/SSH terminal support.
2. **Windows Native Clipboard (`sys.platform == "win32"`):**
   - Primary: Use Python's built-in `ctypes` (`user32.OpenClipboard`, `EmptyClipboard`, `SetClipboardData(CF_UNICODETEXT, ...)`, `kernel32.GlobalAlloc`, `GlobalLock`) for instant, zero-subprocess Unicode clipboard writing without console flashes.
   - Fallback: `subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)`.
3. **macOS / Linux Fallbacks:** `pbcopy` on macOS; `wl-copy` / `xclip` / `xsel` on Linux.

### 3.4 TCSS Selection Styling (`agent/terminal_ui/styles/app.tcss`)

Define a crisp, visible selection highlight style on `Screen`:
```css
Screen {
    & > .screen--selection {
        background: #2563EB 55%;
        color: #F8FAFC;
    }
}
```

---

## 4. Files to Modify

1. `agent/terminal_ui/chat_message.py` (or a dedicated helper module imported by `app.py` / `chat_message.py`):
   - Enable selection support (`RichVisual` offset metadata + selection span highlighting + `_rendered_plain_text` extraction in `Static.get_selection`).
2. `agent/terminal_ui/app.py`:
   - Add `on_text_selected(self, event: events.TextSelected)` handler for OpenCode-style auto-copy on mouse release.
   - Upgrade `_copy_to_clipboard(self, text: str)` with native Windows `ctypes` Unicode clipboard support so both drag-selection and the Copy button work reliably.
3. `agent/terminal_ui/styles/app.tcss`:
   - Configure `.screen--selection` highlight styling.

---

## 5. Verification Criteria

1. Clicking and dragging across any part of a Raven assistant response (headings, paragraphs, bullet lists, inline code, fenced code blocks, tables, or diff blocks) visually highlights the exact character range under the cursor.
2. Dragging across multiple blocks or widgets highlights all spanned blocks in order.
3. Releasing the mouse button after dragging automatically copies the highlighted text to the Windows clipboard and shows `"✓ Copied to clipboard"`.
4. Pressing `Escape` or clicking elsewhere clears the active selection highlight.
5. Clicking the `"Copy"` action button on any message copies the full raw markdown to the Windows clipboard reliably without requiring external packages.
