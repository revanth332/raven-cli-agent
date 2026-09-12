import re
from typing import Any
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from rich.markdown import Markdown
from rich.console import Group


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
    """

    def __init__(self, role: str = "user", raw_text: Any = "", image_badge: str = "", **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.image_badge = image_badge
        self.raw_text = self._format_multimodal_text(raw_text)
        self._pending_renderable = None

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
        yield Static(id="msg_content", classes="msg-content")

    def on_mount(self) -> None:
        if self._pending_renderable is not None:
            pending = self._pending_renderable
            self._pending_renderable = None
            self.update(pending, self.raw_text)
        elif self.raw_text:
            self.update(self.raw_text)

    def update(self, renderable, raw_text: Any = None) -> None:
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
            content_static = self.query_one("#msg_content", Static)
            if isinstance(renderable, (str, list)):
                content_static.update(Markdown(self.raw_text))
            else:
                content_static.update(renderable)
            self._pending_renderable = None
        except Exception:
            self._pending_renderable = renderable

    def on_click(self, event) -> None:
        if event.control and event.control.id == "copy_btn":
            event.stop()
            self.copy_to_clipboard()

    def copy_to_clipboard(self) -> None:
        text_to_copy = self.raw_text
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
