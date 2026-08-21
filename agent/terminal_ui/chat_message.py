from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from rich.markdown import Markdown


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

    .msg-content {
        height: auto;
        width: 100%;
    }
    """

    def __init__(self, role: str = "user", raw_text: str = "", **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.raw_text = raw_text

    def compose(self) -> ComposeResult:
        with Horizontal(classes="msg-header"):
            if self.role == "user":
                yield Static("[bold #06B6D4]YOU[/bold #06B6D4]", classes="msg-role")
            else:
                yield Static("[bold #10B981]RAVEN[/bold #10B981]", classes="msg-role")
            yield Static("Copy", id="copy_btn", classes="copy-btn")
        yield Static(id="msg_content", classes="msg-content")

    def on_mount(self) -> None:
        if self.raw_text:
            self.update(self.raw_text)

    def update(self, renderable, raw_text: str = None) -> None:
        if raw_text:
            self.raw_text = raw_text
        elif isinstance(renderable, str):
            self.raw_text = renderable
        elif hasattr(renderable, "markup") and renderable.markup:
            self.raw_text = renderable.markup

        try:
            content_static = self.query_one("#msg_content", Static)
            if isinstance(renderable, str):
                content_static.update(Markdown(renderable))
            else:
                content_static.update(renderable)
        except Exception:
            pass

    def on_click(self, event) -> None:
        if event.control and event.control.id == "copy_btn":
            event.stop()
            self.copy_to_clipboard()

    def copy_to_clipboard(self) -> None:
        text_to_copy = self.raw_text
        if not text_to_copy:
            try:
                content_static = self.query_one("#msg_content", Static)
                text_to_copy = str(content_static.renderable) if hasattr(content_static, "renderable") else ""
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
