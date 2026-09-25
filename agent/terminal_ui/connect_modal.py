from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Input, Label
from textual.containers import Vertical, Horizontal
from agent.core.settings import settings


class ConnectModal(ModalScreen[dict | None]):
    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    CSS = """
    ConnectModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #modal_container {
        width: 65;
        height: auto;
        max-height: 85%;
        background: #1e1e1e;
        border: heavy #06B6D4;
        padding: 1 2;
    }

    #modal_title {
        text-style: bold;
        color: #06B6D4;
        margin-bottom: 1;
        content-align: center middle;
        text-align: center;
    }

    .field_label {
        color: #94A3B8;
        margin-top: 1;
        margin-bottom: 0;
        text-style: bold;
    }

    .field_input {
        margin-bottom: 1;
        background: #121212;
        border: none;
        color: #F8FAFC;
    }

    #error_label {
        color: #EF4444;
        text-style: italic;
        margin-top: 0;
        margin-bottom: 1;
        display: none;
    }

    #button_container {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    Button {
        margin-left: 1;
        min-width: 12;
        height: 3;
        padding: 0 1;
    }

    #cancel_btn {
        background: transparent;
        color: #E2E8F0;
        border: round #64748B;
    }

    #submit_btn {
        color: #FFFFFF;
        border: round #10B981;
        text-style: bold;
    }
    """

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("Connect to LLM Provider", id="modal_title")

            yield Label("Base URL:", classes="field_label")
            yield Input(
                value="",
                placeholder="e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1",
                id="base_url_input",
                classes="field_input",
            )

            yield Label("API Key:", classes="field_label")
            yield Input(
                value="",
                placeholder="Enter API key",
                password=True,
                id="api_key_input",
                classes="field_input",
            )

            yield Static("", id="error_label")

            with Horizontal(id="button_container"):
                yield Button("Cancel", id="cancel_btn")
                yield Button("Submit", id="submit_btn")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "submit_btn":
            self.submit_credentials()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "base_url_input":
            self.query_one("#api_key_input", Input).focus()
        else:
            self.submit_credentials()

    def submit_credentials(self) -> None:
        base_url = self.query_one("#base_url_input", Input).value.strip()
        api_key = self.query_one("#api_key_input", Input).value.strip()
        error_label = self.query_one("#error_label", Static)

        if not base_url:
            error_label.update("Base URL is required.")
            error_label.styles.display = "block"
            self.query_one("#base_url_input", Input).focus()
            return

        if not api_key:
            error_label.update("API Key is required.")
            error_label.styles.display = "block"
            self.query_one("#api_key_input", Input).focus()
            return

        self.dismiss({
            "base_url": base_url,
            "api_key": api_key
        })
