from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import OptionList, Button, Static, Input
from textual.widgets.option_list import Option
from textual.containers import Vertical, Horizontal
from agent.core.settings import settings

DEFAULT_MODELS = [
    "google/gemini-2.5-flash-preview",
    "google/gemini-2.5-pro",
    "google/gemini-2.0-flash-001",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3.7-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "deepseek/deepseek-r1",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
]

class ModelSelectModal(ModalScreen[str]):
    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    CSS = """
    ModelSelectModal {
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

    #model_list {
        height: 10;
        margin-bottom: 1;
        background: #121212;
        border: none;
    }

    #model_list > .option-list--option {
        padding: 0 1;
    }

    #model_list > .option-list--option-highlighted {
        background: #2d3748;
        color: #38BDF8;
        text-style: bold;
    }

    #custom_input {
        margin-bottom: 1;
        background: #121212;
        border: none;
        color: #F8FAFC;
    }

    #button_container {
        height: auto;
        align: right middle;
    }

    Button {
        margin-left: 1;
        min-width: 10;
        height: 3;
    }

    #cancel_btn {
        background: transparent;
        color: #E2E8F0;
        border: round #64748B;
    }

    #select_btn {
        background: #06B6D4;
        color: #05070B;
        text-style: bold;
        border: none;
    }
    """

    def __init__(self, current_model: str = None) -> None:
        super().__init__()
        self.current_model = current_model or settings.RAVEN_MODEL
        self.models = list(DEFAULT_MODELS)
        if self.current_model and self.current_model not in self.models:
            self.models.insert(0, self.current_model)

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static("Select AI Model", id="modal_title")
            
            ol = OptionList(id="model_list")
            for m in self.models:
                prompt_text = f"• {m}"
                if m == self.current_model:
                    prompt_text += "  [active]"
                ol.add_option(Option(prompt_text, id=m))
            yield ol

            yield Input(placeholder="Or type custom model string...", id="custom_input")
            
            with Horizontal(id="button_container"):
                yield Button("Cancel", id="cancel_btn")
                yield Button("Select", id="select_btn")

    def on_mount(self) -> None:
        # Highlight the current model in the OptionList
        ol = self.query_one("#model_list", OptionList)
        if self.current_model in self.models:
            idx = self.models.index(self.current_model)
            ol.highlighted = idx

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "select_btn":
            self.confirm_selection()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id:
            self.dismiss(option_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.dismiss(val)
        else:
            self.confirm_selection()

    def confirm_selection(self) -> None:
        custom_val = self.query_one("#custom_input", Input).value.strip()
        if custom_val:
            self.dismiss(custom_val)
            return

        ol = self.query_one("#model_list", OptionList)
        if ol.highlighted is not None and ol.highlighted < len(self.models):
            selected_model = self.models[ol.highlighted]
            self.dismiss(selected_model)
        else:
            self.dismiss(None)
