import re
from dataclasses import dataclass
from typing import Any, List, Optional
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from rich.markdown import Markdown
from rich.console import Group, RenderableType
from rich.text import Text

MAX_DIFF_LINES = 8
MAX_ARG_LENGTH = 80
MAX_RESULT_LINES = 6


def format_tool_header(display_name: str, display_value: str = "", tool_name: str = "") -> Text:
    """Formats a tool invocation header Text renderable."""
    tool_logs = Text()
    tool_logs.append("\n• ", style="bold cyan")
    tool_logs.append(display_name, style="bold cyan")
    if display_value:
        clean_val = " ".join(str(display_value).split())
        max_len = 120 if tool_name == "search_codebase" else MAX_ARG_LENGTH
        if len(clean_val) > max_len:
            clean_val = clean_val[: max_len - 3] + "..."
        tool_logs.append("(", style="dim white")
        tool_logs.append(clean_val, style="dim white")
        tool_logs.append(")", style="dim white")
    tool_logs.append("\n")
    return tool_logs


def format_patch_diff(
    file_path: str,
    search_block: str,
    replace_block: str,
    include_header: bool = False,
    expanded: bool = False,
    result_str: str = "",
) -> Text:
    """Formats a syntax-highlighted git/patch diff preview with expandable lines."""
    tool_logs = Text()
    if include_header:
        tool_logs.append(format_tool_header("Update", file_path))

    if search_block or replace_block:
        search_block_lines = search_block.rstrip().split("\n") if search_block else []
        replace_block_lines = replace_block.rstrip().split("\n") if replace_block else []
        search_count = len(search_block_lines)
        replace_count = len(replace_block_lines)

        tool_logs.append("   |_ Updated ", style="dim white")
        tool_logs.append(f"{file_path} ")
        tool_logs.append("with ", style="dim white")
        tool_logs.append(f"{replace_count} ", style="bold green" if replace_count else "dim white")
        tool_logs.append("addition" if replace_count == 1 else "additions", style="dim white")
        tool_logs.append(" and ", style="dim white")
        tool_logs.append(f"{search_count} ", style="bold red" if search_count else "dim white")
        tool_logs.append("removal\n" if search_count == 1 else "removals\n", style="dim white")

        if result_str and "SYNTAX VERIFICATION WARNING" in result_str:
            tool_logs.append("   |_ ⚠ Syntax Warning Detected\n", style="bold yellow")
            for w_line in result_str.splitlines():
                if any(k in w_line for k in ("Details:", "Syntax", "Error:", "JSONDecodeError", "SyntaxError")):
                    tool_logs.append(f"       {w_line.strip()}\n", style="yellow")

        diff_limit = 1000 if expanded else MAX_DIFF_LINES

        if search_block_lines:
            visible_search = search_block_lines[:diff_limit]
            for line in visible_search:
                tool_logs.append("       ")
                tool_logs.append(f"- {line}\n", style="white on #961b1b")
            collapsed_search = search_count - len(visible_search)
            if collapsed_search > 0:
                tool_logs.append(f"       ▶ ... [{collapsed_search} search lines collapsed - click to expand]\n", style="dim cyan italic")

        if replace_block_lines:
            visible_replace = replace_block_lines[:diff_limit]
            for line in visible_replace:
                tool_logs.append("       ")
                tool_logs.append(f"+ {line}\n", style="white on #26753a")
            collapsed_replace = replace_count - len(visible_replace)
            if collapsed_replace > 0:
                tool_logs.append(f"       ▶ ... [{collapsed_replace} replace lines collapsed - click to expand]\n", style="dim cyan italic")

        if expanded and (search_count > MAX_DIFF_LINES or replace_count > MAX_DIFF_LINES):
            tool_logs.append("       ▼ [Click to collapse]\n", style="dim cyan italic")

    return tool_logs


def format_command_result(command: str, raw_output: str, expanded: bool = False) -> Text:
    """Formats a concise preview of command execution results with expansion."""
    result_text = Text()
    lines = str(raw_output).splitlines()
    exit_code = 0
    stdout_lines = []
    stderr_lines = []
    in_stdout = False
    in_stderr = False

    for line in lines:
        if line.startswith("Exit Code:"):
            try:
                exit_code = int(line.split(":", 1)[1].strip())
            except Exception:
                exit_code = 0
        elif line.startswith("STDOUT:"):
            in_stdout = True
            in_stderr = False
        elif line.startswith("STDERR:"):
            in_stdout = False
            in_stderr = True
        elif in_stdout:
            stdout_lines.append(line)
        elif in_stderr:
            stderr_lines.append(line)
        else:
            stdout_lines.append(line)

    limit = 1000 if expanded else MAX_RESULT_LINES

    if exit_code == 0:
        result_text.append("   |_ Exit 0\n", style="bold green")
        clean_lines = [l for l in stdout_lines if l.strip()]
        if clean_lines:
            visible_lines = clean_lines[:limit]
            for l in visible_lines:
                clean_l = l if len(l) <= 120 else l[:117] + "..."
                result_text.append(f"       {clean_l}\n", style="dim white")
            collapsed = len(clean_lines) - len(visible_lines)
            if collapsed > 0:
                result_text.append(f"       ▶ ... [{collapsed} lines collapsed - click to expand]\n", style="dim cyan italic")
            elif expanded and len(clean_lines) > MAX_RESULT_LINES:
                result_text.append("       ▼ [Click to collapse]\n", style="dim cyan italic")
    else:
        result_text.append(f"   |_ Exit Code: {exit_code} (Failed)\n", style="bold red")
        error_lines = [l for l in (stderr_lines or stdout_lines) if l.strip()]
        if error_lines:
            visible_lines = error_lines[:limit]
            for l in visible_lines:
                clean_l = l if len(l) <= 120 else l[:117] + "..."
                result_text.append(f"       {clean_l}\n", style="red")
            collapsed = len(error_lines) - len(visible_lines)
            if collapsed > 0:
                result_text.append(f"       ▶ ... [{collapsed} error lines collapsed - click to expand]\n", style="dim cyan italic")
            elif expanded and len(error_lines) > MAX_RESULT_LINES:
                result_text.append("       ▼ [Click to collapse]\n", style="dim cyan italic")
    return result_text


def format_read_result(file_path: str, content: str, expanded: bool = False) -> Text:
    """Formats file read results showing line count and expandable content."""
    result_text = Text()
    content_str = str(content)
    if content_str.startswith("Error:") or content_str.startswith("ACCESS DENIED"):
        result_text.append(f"   |_ {content_str.strip()}\n", style="bold red")
        return result_text

    lines = content_str.splitlines()
    num_lines = len(lines)
    size_bytes = len(content_str.encode("utf-8", errors="ignore"))
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

    line_word = "line" if num_lines == 1 else "lines"
    result_text.append(f"   |_ Read {num_lines} {line_word} ({size_str})\n", style="dim white")

    if expanded and lines:
        limit = 50
        visible_lines = lines[:limit]
        for l in visible_lines:
            clean_l = l if len(l) <= 100 else l[:97] + "..."
            result_text.append(f"       {clean_l}\n", style="dim white")
        collapsed = num_lines - len(visible_lines)
        if collapsed > 0:
            result_text.append(f"       ... [{collapsed} more lines]\n", style="dim italic white")
        result_text.append("       ▼ [Click to collapse]\n", style="dim cyan italic")
    elif not expanded and num_lines > 4:
        result_text.append("       ▶ ... [Click to view file content]\n", style="dim cyan italic")

    return result_text


def format_find_result(file_name: str, result_str: str, expanded: bool = False) -> Text:
    """Formats file search results showing match count or paths."""
    result_text = Text()
    clean = str(result_str).strip()
    if "not found" in clean.lower():
        result_text.append(f"   |_ {clean}\n", style="dim yellow")
    elif "access denied" in clean.lower():
        result_text.append(f"   |_ {clean}\n", style="bold red")
    else:
        try:
            import ast
            parsed = ast.literal_eval(clean)
            if isinstance(parsed, list):
                if not parsed:
                    result_text.append("   |_ No matching files found\n", style="dim yellow")
                elif len(parsed) == 1:
                    result_text.append(f"   |_ Found: {parsed[0]}\n", style="dim white")
                else:
                    count = len(parsed)
                    if expanded:
                        result_text.append(f"   |_ Found {count} files:\n", style="dim white")
                        for p in parsed:
                            result_text.append(f"       {p}\n", style="dim white")
                        result_text.append("       ▼ [Click to collapse]\n", style="dim cyan italic")
                    else:
                        preview = ", ".join(parsed[:2])
                        if count > 2:
                            preview += f", ... (+{count - 2} more)"
                        result_text.append(f"   |_ Found {count} files: {preview}\n", style="dim white")
                        if count > 2:
                            result_text.append("       ▶ ... [Click to view all matches]\n", style="dim cyan italic")
                return result_text
        except Exception:
            pass
        if len(clean) > 80 and not expanded:
            clean = clean[:77] + "..."
        result_text.append(f"   |_ Found: {clean}\n", style="dim white")
    return result_text


def format_generic_tool_result(tool_name: str, result: Any, expanded: bool = False) -> Text:
    """Formats a concise fallback preview for any tool result."""
    result_text = Text()
    clean = str(result).strip()
    if clean.startswith("Error:") or clean.startswith("ACCESS DENIED"):
        result_text.append(f"   |_ {clean}\n", style="bold red")
    else:
        lines = [l for l in clean.splitlines() if l.strip()]
        if not lines:
            result_text.append("   |_ Completed\n", style="dim white")
            return result_text

        if len(lines) == 1 or not expanded:
            first_line = lines[0]
            if len(first_line) > 100:
                first_line = first_line[:97] + "..."
            result_text.append(f"   |_ {first_line}\n", style="dim white")
            if len(lines) > 1 and not expanded:
                result_text.append(f"       ▶ ... [{len(lines) - 1} more lines - click to expand]\n", style="dim cyan italic")
        else:
            result_text.append(f"   |_ {lines[0]}\n", style="dim white")
            for l in lines[1:20]:
                clean_l = l if len(l) <= 100 else l[:97] + "..."
                result_text.append(f"       {clean_l}\n", style="dim white")
            if len(lines) > 20:
                result_text.append(f"       ... [{len(lines) - 20} more lines]\n", style="dim italic white")
            result_text.append("       ▼ [Click to collapse]\n", style="dim cyan italic")
    return result_text


def format_search_content_result(query: str, result_str: str, expanded: bool = False) -> Text:
    """Formats grep search results showing match count and expandable snippet."""
    result_text = Text()
    clean = str(result_str).strip()
    if clean.startswith("No matches found") or "not found" in clean.lower():
        result_text.append(f"   |_ {clean}\n", style="dim yellow")
    elif clean.startswith("ACCESS DENIED") or clean.startswith("Error:"):
        result_text.append(f"   |_ {clean}\n", style="bold red")
    else:
        lines = [l for l in clean.splitlines() if l.strip()]
        file_headers = [l for l in lines if l.startswith("--- ") and l.endswith(" ---")]
        match_count = sum(1 for l in lines if l.startswith(">"))
        file_count = len(file_headers)

        summary = f"Found {match_count} match" if match_count == 1 else f"Found {match_count} matches"
        if file_count > 0:
            summary += f" across {file_count} file" if file_count == 1 else f" across {file_count} files"

        result_text.append(f"   |_ {summary}\n", style="dim white")

        if expanded and lines:
            limit = 60
            visible_lines = lines[:limit]
            for l in visible_lines:
                if l.startswith("--- ") and l.endswith(" ---"):
                    result_text.append(f"       {l}\n", style="bold cyan")
                elif l.startswith(">"):
                    result_text.append(f"     {l}\n", style="white on #1e3a5f")
                else:
                    clean_l = l if len(l) <= 120 else l[:117] + "..."
                    result_text.append(f"     {clean_l}\n", style="dim white")
            collapsed = len(lines) - len(visible_lines)
            if collapsed > 0:
                result_text.append(f"       ... [{collapsed} more lines]\n", style="dim italic white")
            result_text.append("       ▼ [Click to collapse]\n", style="dim cyan italic")
        elif not expanded and lines:
            preview_line = file_headers[0] if file_headers else lines[0]
            result_text.append(f"       {preview_line}\n", style="dim white")
            result_text.append("       ▶ ... [Click to view matches & context]\n", style="dim cyan italic")

    return result_text


def format_checkpoint_result(tool_name: str, result_str: str, expanded: bool = False) -> Text:
    """Formats checkpoint and rollback tool feedback."""
    result_text = Text()
    clean = str(result_str).strip()
    if clean.startswith("Error:") or clean.startswith("Failed"):
        result_text.append(f"   |_ {clean}\n", style="bold red")
    else:
        lines = [l for l in clean.splitlines() if l.strip()]
        if not lines:
            result_text.append("   |_ Checkpoint completed\n", style="bold green")
            return result_text
        
        header_style = "bold green" if "Successfully" in lines[0] else "dim white"
        result_text.append(f"   |_ {lines[0]}\n", style=header_style)
        for line in lines[1:]:
            result_text.append(f"       {line}\n", style="dim white")
    return result_text


def format_tool_result_preview(
    tool_name: str,
    tool_args: dict,
    result: Any,
    expanded: bool = False,
) -> Text:
    """Dispatches to the appropriate tool result formatter."""
    args = tool_args or {}
    if tool_name == "patch_file":
        search_block = args.get("search_block", "")
        replace_block = args.get("replace_block", "")
        file_path = args.get("file_path", "Unknown")
        if search_block or replace_block:
            return format_patch_diff(file_path, search_block, replace_block, expanded=expanded, result_str=str(result or ""))
        return format_generic_tool_result(tool_name, result, expanded=expanded)
    elif tool_name == "execute_command":
        cmd = args.get("command", "")
        return format_command_result(cmd, str(result), expanded=expanded)
    elif tool_name == "read_file":
        file_path = args.get("file_path", "")
        return format_read_result(file_path, str(result), expanded=expanded)
    elif tool_name == "find_file":
        file_name = args.get("file_name", "")
        return format_find_result(file_name, str(result), expanded=expanded)
    elif tool_name == "search_file_content":
        query = args.get("query", "")
        return format_search_content_result(query, str(result), expanded=expanded)
    elif tool_name in ("create_checkpoint", "rollback_checkpoint", "list_checkpoints"):
        return format_checkpoint_result(tool_name, str(result), expanded=expanded)
    else:
        return format_generic_tool_result(tool_name, result, expanded=expanded)


@dataclass
class TextBlock:
    content: str = ""


@dataclass
class ToolCallBlock:
    tool_name: str
    display_name: str
    display_val: str = ""
    status: str = "running"  # "running", "completed", "error", "denied"


@dataclass
class ToolResultBlock:
    tool_name: str
    renderable: Any = None
    plain_text: str = ""
    tool_args: dict = None
    raw_result: Any = None
    expanded: bool = False


@dataclass
class StatusBlock:
    message: str
    style: str = "dim white"


class ResponseTimeline:
    """Maintains a chronological sequence of text, tool call, and result blocks for an agent response."""

    def __init__(self):
        self.blocks: List[Any] = []

    def append_text(self, text: str) -> None:
        """Appends streaming delta text into the current active TextBlock."""
        if not text:
            return
        if self.blocks and isinstance(self.blocks[-1], TextBlock):
            self.blocks[-1].content += text
        else:
            self.blocks.append(TextBlock(content=text))

    def add_tool_call(self, tool_name: str, display_name: str, display_val: str = "", status: str = "running") -> None:
        """Appends a tool invocation header to the timeline."""
        self.blocks.append(ToolCallBlock(
            tool_name=tool_name,
            display_name=display_name,
            display_val=display_val,
            status=status,
        ))

    def add_tool_result(
        self,
        tool_name: str,
        renderable: Any = None,
        plain_text: str = "",
        tool_args: dict = None,
        raw_result: Any = None,
        expanded: bool = False,
    ) -> None:
        """Appends a tool execution result preview to the timeline and updates tool status."""
        for block in reversed(self.blocks):
            if isinstance(block, ToolCallBlock) and block.tool_name == tool_name and block.status == "running":
                block.status = "completed"
                break
        self.blocks.append(ToolResultBlock(
            tool_name=tool_name,
            renderable=renderable,
            plain_text=plain_text or (renderable.plain if hasattr(renderable, "plain") else str(renderable or "")),
            tool_args=tool_args or {},
            raw_result=raw_result,
            expanded=expanded,
        ))

    def add_status(self, message: str, style: str = "dim white") -> None:
        """Appends an operational status or timing note to the timeline."""
        self.blocks.append(StatusBlock(message=message, style=style))

    def to_renderables(self) -> list:
        """Compiles the timeline into a list of Rich renderables."""
        renderables = []
        for block in self.blocks:
            if isinstance(block, TextBlock):
                if block.content.strip():
                    renderables.append(Markdown(block.content))
            elif isinstance(block, ToolCallBlock):
                header = format_tool_header(block.display_name, block.display_val, block.tool_name)
                renderables.append(header)
                if block.status == "running":
                    running_text = Text("   |_ Running...\n", style="dim cyan italic")
                    renderables.append(running_text)
            elif isinstance(block, ToolResultBlock):
                if block.raw_result is not None or (block.tool_args and block.renderable is None):
                    formatted = format_tool_result_preview(
                        block.tool_name,
                        block.tool_args,
                        block.raw_result,
                        expanded=block.expanded,
                    )
                    renderables.append(formatted)
                elif block.renderable is not None:
                    renderables.append(block.renderable)
            elif isinstance(block, StatusBlock):
                renderables.append(Text(f"\n{block.message}\n", style=block.style))
        return renderables

    def to_renderable(self) -> Group:
        """Compiles the timeline into a Rich Group for Textual rendering."""
        renderables = self.to_renderables()
        if not renderables:
            return Group(Text(""))
        return Group(*renderables)

    def to_plain_text(self) -> str:
        """Produces a clean plain-text transcript suitable for clipboard copying."""
        parts = []
        for block in self.blocks:
            if isinstance(block, TextBlock):
                clean = block.content.strip()
                if clean:
                    parts.append(clean)
            elif isinstance(block, ToolCallBlock):
                header = format_tool_header(block.display_name, block.display_val, block.tool_name)
                parts.append(header.plain.strip())
            elif isinstance(block, ToolResultBlock):
                if block.raw_result is not None or (block.tool_args and block.renderable is None):
                    formatted = format_tool_result_preview(
                        block.tool_name,
                        block.tool_args,
                        block.raw_result,
                        expanded=block.expanded,
                    )
                    parts.append(formatted.plain.strip())
                elif block.plain_text:
                    parts.append(block.plain_text.strip())
                elif hasattr(block.renderable, "plain") and block.renderable.plain:
                    parts.append(block.renderable.plain.strip())
            elif isinstance(block, StatusBlock):
                clean = block.message.strip()
                if clean:
                    parts.append(clean)
        return "\n\n".join(parts)

    def is_empty(self) -> bool:
        """Checks if the timeline contains any meaningful content."""
        for block in self.blocks:
            if isinstance(block, TextBlock) and block.content.strip():
                return False
            if isinstance(block, (ToolCallBlock, ToolResultBlock, StatusBlock)):
                return False
        return True


class ToolResultWidget(Static):
    """Interactive widget for an individual tool result preview that expands/collapses on click."""

    DEFAULT_CSS = """
    ToolResultWidget {
        height: auto;
        width: 100%;
    }
    """

    def __init__(self, block: ToolResultBlock, parent_widget: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.block = block
        self.parent_widget = parent_widget

    def on_mount(self) -> None:
        self.refresh_preview()

    def refresh_preview(self) -> None:
        preview = format_tool_result_preview(
            self.block.tool_name,
            self.block.tool_args,
            self.block.raw_result,
            expanded=self.block.expanded,
        )
        self.update(preview)

    def on_click(self, event) -> None:
        event.stop()
        self.block.expanded = not self.block.expanded
        self.refresh_preview()
        if self.parent_widget and getattr(self.parent_widget, "_timeline", None):
            self.parent_widget.raw_text = self.parent_widget._timeline.to_plain_text()


class ChatMessageWidget(Vertical):
    DEFAULT_CSS = """
    ChatMessageWidget {
        margin: 1 0;
        padding: 1 2;
        height: auto;
        width: 100%;
        background: #1e1e1e;
    }

    ChatMessageWidget.user-msg {
        color: #F8FAFC;
        background: #1e1e1e;
        border-left: heavy #06B6D4;
    }

    ChatMessageWidget.raven-msg {
        color: #ECFDF5;
        background: #1e1e1e;
        border-left: heavy #10B981;
    }

    .msg-header {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }

    .msg-role {
        text-style: bold;
        height: 1;
        width: 1fr;
    }

    .copy-btn {
        width: auto;
        height: 1;
        padding: 0 1;
        color: #64748B;
        background: transparent;
        text-align: right;
        content-align: right middle;
    }

    .copy-btn:hover {
        color: #38BDF8;
        background: #27272a;
    }

    .img-badge {
        color: #06B6D4;
        text-style: bold;
        height: auto;
        margin-bottom: 1;
    }

    .msg-content {
        height: auto;
        width: 100%;
    }

    .timeline-container {
        height: auto;
        width: 100%;
    }

    .timeline-item {
        height: auto;
        width: 100%;
    }
    """

    def __init__(
        self,
        role: str = "user",
        raw_text: Any = "",
        image_badge: str = "",
        timeline: Optional[ResponseTimeline] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.role = role
        self.image_badge = image_badge
        self.raw_text = self._format_multimodal_text(raw_text)
        self._timeline: Optional[ResponseTimeline] = timeline
        self._pending_renderable = timeline if timeline is not None else None

    def _format_multimodal_text(self, content: Any) -> str:
        if isinstance(content, str):
            # Intercept any legacy or direct rich markup badge like [bold #06B6D4][...][/bold #06B6D4]
            markup_pattern = r"^\[bold\s+#[0-9a-fA-F]{6}\]\[?(.*?)\]?\[/bold\s+#[0-9a-fA-F]{6}\]\s*\n*"
            match = re.match(markup_pattern, content)
            if match:
                badge_text = match.group(1).strip()
                clean_badge = badge_text.replace("🖼️", "").replace("🖼", "").strip("[] ")
                if clean_badge and not self.image_badge:
                    self.image_badge = clean_badge
                return content[match.end():].strip()
            return content

        if isinstance(content, list):
            text_parts = []
            has_image = False
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        has_image = True

            if has_image and not self.image_badge:
                self.image_badge = "Attached Image"
            body = "\n\n".join(t for t in text_parts if t.strip())
            return body or str(content)
        return str(content) if content is not None else ""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="msg-header"):
            if self.role == "user":
                yield Static("[bold #06B6D4]YOU[/bold #06B6D4]", classes="msg-role")
            else:
                yield Static("[bold #10B981]RAVEN[/bold #10B981]", classes="msg-role")
            yield Static("Copy", id="copy_btn", classes="copy-btn")
        if self.image_badge:
            yield Static(f"[bold #06B6D4]◆ Image: {self.image_badge}[/bold #06B6D4]", id="img_badge", classes="img-badge")
        yield Vertical(id="timeline_container", classes="timeline-container")
        yield Static(id="msg_content", classes="msg-content")

    def _sync_timeline_widgets(self) -> None:
        """Syncs child widgets in timeline_container with self._timeline.blocks."""
        if not self._timeline:
            return

        try:
            container = self.query_one("#timeline_container", Vertical)
            content_static = self.query_one("#msg_content", Static)
            content_static.display = False
            container.display = True
        except Exception:
            return

        blocks = self._timeline.blocks
        children = list(container.children)

        # Update existing widgets or mount new ones
        for idx, block in enumerate(blocks):
            if idx < len(children):
                child = children[idx]
                if isinstance(block, TextBlock) and isinstance(child, Static):
                    child.update(Markdown(block.content) if block.content.strip() else Text(""))
                elif isinstance(block, ToolCallBlock) and isinstance(child, Static):
                    child.update(format_tool_header(block.display_name, block.display_val, block.tool_name))
                elif isinstance(block, ToolResultBlock) and isinstance(child, ToolResultWidget):
                    child.block = block
                    child.refresh_preview()
                elif isinstance(block, StatusBlock) and isinstance(child, Static):
                    child.update(Text(f"\n{block.message}\n", style=block.style))
            else:
                # Mount new widget for new block
                if isinstance(block, TextBlock):
                    w = Static(Markdown(block.content) if block.content.strip() else Text(""), classes="timeline-item")
                elif isinstance(block, ToolCallBlock):
                    w = Static(format_tool_header(block.display_name, block.display_val, block.tool_name), classes="timeline-item")
                elif isinstance(block, ToolResultBlock):
                    w = ToolResultWidget(block, parent_widget=self, classes="timeline-item")
                elif isinstance(block, StatusBlock):
                    w = Static(Text(f"\n{block.message}\n", style=block.style), classes="timeline-item")
                else:
                    w = Static(classes="timeline-item")
                container.mount(w)

    def on_mount(self) -> None:
        if self._timeline is not None:
            self.raw_text = self._timeline.to_plain_text()
            self._sync_timeline_widgets()
            self._pending_renderable = None
        elif self._pending_renderable is not None:
            pending = self._pending_renderable
            self._pending_renderable = None
            self.update(pending, self.raw_text)
        elif self.raw_text:
            self.update(self.raw_text)

    def update(self, renderable, raw_text: Any = None) -> None:
        if isinstance(renderable, ResponseTimeline):
            self._timeline = renderable
            self.raw_text = renderable.to_plain_text()
            self._pending_renderable = renderable
            self._sync_timeline_widgets()
            return

        self._timeline = None
        if isinstance(renderable, Group):
            group_texts = []
            for item in renderable.renderables:
                if hasattr(item, "plain") and item.plain:
                    clean = item.plain.strip()
                    if clean:
                        group_texts.append(clean)
            if raw_text is not None:
                clean_raw = self._format_multimodal_text(raw_text).strip()
                if clean_raw:
                    group_texts.append(clean_raw)
            if group_texts:
                self.raw_text = "\n\n".join(group_texts)
            elif raw_text is not None:
                self.raw_text = self._format_multimodal_text(raw_text)
        elif raw_text is not None:
            self.raw_text = self._format_multimodal_text(raw_text)
        elif isinstance(renderable, (str, list)):
            self.raw_text = self._format_multimodal_text(renderable)
        elif hasattr(renderable, "plain") and renderable.plain:
            self.raw_text = renderable.plain

        try:
            container = self.query_one("#timeline_container", Vertical)
            container.display = False
            content_static = self.query_one("#msg_content", Static)
            content_static.display = True
            if isinstance(renderable, (str, list)):
                content_static.update(Markdown(self.raw_text))
            else:
                content_static.update(renderable)
            self._pending_renderable = None
        except Exception:
            self._pending_renderable = renderable

    def update_timeline(self, timeline: ResponseTimeline) -> None:
        """Helper to update widget directly from a ResponseTimeline."""
        self.update(timeline)

    def toggle_tool_expansion(self, index: int = -1) -> bool:
        """Toggles expansion of tool result block(s). If index is -1, toggles all tool blocks."""
        if not self._timeline:
            return False
        tool_blocks = [b for b in self._timeline.blocks if isinstance(b, ToolResultBlock)]
        if not tool_blocks:
            return False

        if 0 <= index < len(tool_blocks):
            tool_blocks[index].expanded = not tool_blocks[index].expanded
        else:
            for b in tool_blocks:
                b.expanded = not b.expanded

        self.update_timeline(self._timeline)
        return True

    def on_click(self, event) -> None:
        if event.control and event.control.id == "copy_btn":
            event.stop()
            self.copy_to_clipboard()
            return

    def copy_to_clipboard(self) -> None:
        text_to_copy = self.raw_text
        if not text_to_copy and self._timeline:
            text_to_copy = self._timeline.to_plain_text()

        if not text_to_copy:
            try:
                content_static = self.query_one("#msg_content", Static)
                renderable = getattr(content_static, "renderable", None)
                if hasattr(renderable, "plain") and renderable.plain:
                    text_to_copy = renderable.plain
                elif hasattr(renderable, "markup") and renderable.markup:
                    text_to_copy = renderable.markup
                else:
                    text_to_copy = str(renderable) if renderable is not None else ""
            except Exception:
                text_to_copy = ""

        if not text_to_copy:
            return

        try:
            self.app.copy_to_clipboard(text_to_copy)
        except Exception:
            pass

        try:
            import pyperclip
            pyperclip.copy(text_to_copy)
        except Exception:
            pass

        try:
            btn = self.query_one("#copy_btn", Static)
            btn.update("✓ Copied!")

            def reset_btn() -> None:
                try:
                    btn.update("Copy")
                except Exception:
                    pass

            self.set_timer(2.0, reset_btn)
        except Exception:
            pass

        try:
            self.app.notify("Message copied to clipboard!", title="Clipboard", severity="information")
        except Exception:
            pass
