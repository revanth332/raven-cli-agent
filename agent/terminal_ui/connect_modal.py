from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Input, Label, Select, RadioSet, RadioButton
from textual.containers import Vertical, Horizontal
from agent.core.settings import settings
from agent.core.preset_manager import (
    load_presets,
    save_preset,
    delete_preset,
    get_active_preset,
    set_active_preset,
    BUILTIN_PRESETS,
)


class ConnectModal(ModalScreen[dict | None]):
    BINDINGS = [("escape", "dismiss_modal", "Cancel")]
    CSS_PATH = "styles/connect_modal.tcss"

    def __init__(self) -> None:
        super().__init__()
        data = load_presets()
        self.presets = data.get("presets", {})
        self.active_preset_name, self.active_preset_cfg = get_active_preset()

    def _build_preset_options(self) -> list[tuple[str, str]]:
        options = []
        for name, cfg in self.presets.items():
            ptype = cfg.get("provider_type", "openai").upper()
            options.append((f"{name} ({ptype})", name))
        options.append(("[+ New Custom Provider]", "__new__"))
        return options

    def compose(self) -> ComposeResult:
        options = self._build_preset_options()
        initial_val = self.active_preset_name if self.active_preset_name in self.presets else (options[0][1] if options else "__new__")

        cfg = self.presets.get(initial_val, {})
        is_vertex = bool(cfg.get("use_vertex_ai") or cfg.get("provider_type") == "vertex")

        preset_name = initial_val if initial_val != "__new__" else ""
        base_url = "" if is_vertex else (cfg.get("base_url") or "")
        api_key = "" if is_vertex else (cfg.get("api_key") or "")
        delete_disabled = (initial_val in BUILTIN_PRESETS) or (initial_val == "__new__")

        with Vertical(id="modal_container"):
            yield Static("Configure Provider & Presets", id="modal_title")

            yield Label("Provider Preset:", classes="field_label")
            yield Select(
                options=options,
                value=initial_val,
                allow_blank=False,
                id="preset_select",
            )

            yield Label("Provider Type:", classes="field_label")
            with RadioSet(id="provider_type_radios"):
                yield RadioButton("OpenAI-Compatible Endpoint", id="radio_openai", value=not is_vertex)
                yield RadioButton("Google Vertex AI", id="radio_vertex", value=is_vertex)

            yield Label("Preset Name:", classes="field_label")
            yield Input(
                value=preset_name,
                placeholder="Enter preset name",
                id="preset_name_input",
                classes="field_input",
            )

            yield Label("Base URL:", classes="field_label", id="base_url_label")
            yield Input(
                value=base_url,
                placeholder="Optional custom OpenAPI endpoint or leave blank for default" if is_vertex else "e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1",
                id="base_url_input",
                classes="field_input",
            )

            yield Label("API Key:", classes="field_label", id="api_key_label")
            yield Input(
                value=api_key,
                placeholder="Auto-generated via Google Cloud ADC" if is_vertex else "Enter API key",
                password=True,
                id="api_key_input",
                classes="field_input",
                disabled=is_vertex,
            )

            yield Static("", id="error_label")

            with Horizontal(id="button_container"):
                yield Button("Delete Preset", id="delete_btn", disabled=delete_disabled)
                yield Button("Cancel", id="cancel_btn")
                yield Button("Save & Connect", id="save_btn")
                yield Button("Connect", id="submit_btn")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "preset_select":
            return
        selected_val = str(event.value)
        if selected_val in (str(Select.BLANK), str(Select.NULL), ""):
            return

        self._apply_preset_to_inputs(selected_val)

    def _apply_preset_to_inputs(self, preset_key: str) -> None:
        preset_name_input = self.query_one("#preset_name_input", Input)
        base_url_input = self.query_one("#base_url_input", Input)
        api_key_input = self.query_one("#api_key_input", Input)
        delete_btn = self.query_one("#delete_btn", Button)
        error_label = self.query_one("#error_label", Static)
        error_label.styles.display = "none"

        if preset_key == "__new__":
            preset_name_input.value = ""
            preset_name_input.placeholder = "Enter custom preset name"
            self.query_one("#radio_openai", RadioButton).value = True
            base_url_input.value = ""
            base_url_input.disabled = False
            base_url_input.placeholder = "e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1"
            api_key_input.value = ""
            api_key_input.disabled = False
            api_key_input.placeholder = "Enter API key"
            delete_btn.disabled = True
        else:
            cfg = self.presets.get(preset_key, {})
            preset_name_input.value = preset_key
            is_vertex = bool(cfg.get("use_vertex_ai") or cfg.get("provider_type") == "vertex")

            if is_vertex:
                self.query_one("#radio_vertex", RadioButton).value = True
                base_url_input.value = cfg.get("base_url") or ""
                base_url_input.disabled = False
                base_url_input.placeholder = "Optional custom OpenAPI endpoint or leave blank for default"
                api_key_input.value = ""
                api_key_input.disabled = True
                api_key_input.placeholder = "Auto-generated via Google Cloud ADC"
            else:
                self.query_one("#radio_openai", RadioButton).value = True
                base_url_input.disabled = False
                base_url_input.value = cfg.get("base_url") or ""
                base_url_input.placeholder = "e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1"
                api_key_input.disabled = False
                api_key_input.value = cfg.get("api_key") or ""
                api_key_input.placeholder = "Enter API key"

            delete_btn.disabled = (preset_key in BUILTIN_PRESETS)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "provider_type_radios":
            return
        is_vertex = (event.pressed.id == "radio_vertex")
        base_url_input = self.query_one("#base_url_input", Input)
        api_key_input = self.query_one("#api_key_input", Input)
        error_label = self.query_one("#error_label", Static)
        error_label.styles.display = "none"

        if is_vertex:
            base_url_input.disabled = False
            base_url_input.placeholder = "Optional custom OpenAPI endpoint or leave blank for default"
            api_key_input.disabled = True
            api_key_input.value = ""
            api_key_input.placeholder = "Auto-generated via Google Cloud ADC"
        else:
            base_url_input.disabled = False
            base_url_input.placeholder = "e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1"
            api_key_input.disabled = False
            api_key_input.placeholder = "Enter API key"
            curr_name = self.query_one("#preset_name_input", Input).value.strip()
            if curr_name in self.presets:
                cfg = self.presets[curr_name]
                if cfg.get("base_url") and not base_url_input.value:
                    base_url_input.value = cfg["base_url"]
                if cfg.get("api_key") and not api_key_input.value:
                    api_key_input.value = cfg["api_key"]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "delete_btn":
            self.delete_current_preset()
        elif event.button.id == "save_btn":
            self.submit_credentials(save=True)
        elif event.button.id == "submit_btn":
            self.submit_credentials(save=False)

    def delete_current_preset(self) -> None:
        select = self.query_one("#preset_select", Select)
        sel_val = str(select.value)
        if not sel_val or sel_val == "__new__" or sel_val in BUILTIN_PRESETS:
            return

        try:
            delete_preset(sel_val)
        except Exception as e:
            error_label = self.query_one("#error_label", Static)
            error_label.update(str(e))
            error_label.styles.display = "block"
            return

        self.presets = load_presets().get("presets", {})
        options = self._build_preset_options()
        active_name, _ = get_active_preset()
        target_val = active_name if active_name in self.presets else options[0][1]

        select.set_options(options)
        select.value = target_val
        self._apply_preset_to_inputs(target_val)
        self.notify(f"Deleted preset '{sel_val}'", title="Preset Deleted", severity="information")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "preset_name_input":
            base_url = self.query_one("#base_url_input", Input)
            if not base_url.disabled:
                base_url.focus()
            else:
                self.submit_credentials(save=False)
        elif event.input.id == "base_url_input":
            self.query_one("#api_key_input", Input).focus()
        else:
            self.submit_credentials(save=False)

    def submit_credentials(self, save: bool = False) -> None:
        is_vertex = self.query_one("#radio_vertex", RadioButton).value
        preset_name = self.query_one("#preset_name_input", Input).value.strip()
        base_url = self.query_one("#base_url_input", Input).value.strip()
        api_key = self.query_one("#api_key_input", Input).value.strip()
        error_label = self.query_one("#error_label", Static)

        if save and not preset_name:
            error_label.update("Preset name is required to save.")
            error_label.styles.display = "block"
            self.query_one("#preset_name_input", Input).focus()
            return

        if is_vertex:
            target_preset = preset_name or "Google Vertex AI"
            existing = self.presets.get(target_preset, {})
            default_model = existing.get("default_model") or "google/gemini-2.5-flash"
            result = {
                "preset_name": target_preset,
                "provider_type": "vertex",
                "use_vertex_ai": True,
                "base_url": base_url or None,
                "api_key": None,
                "default_model": default_model,
            }
            if save:
                save_preset(target_preset, result, set_as_active=True)
            else:
                if target_preset in self.presets:
                    set_active_preset(target_preset)
            self.dismiss(result)
            return

        # OpenAI compatible validation
        if not base_url:
            error_label.update("Base URL is required.")
            error_label.styles.display = "block"
            self.query_one("#base_url_input", Input).focus()
            return

        if not api_key:
            if any(loc in base_url.lower() for loc in ["localhost", "127.0.0.1", "ollama", ":11434"]):
                api_key = "ollama"
            else:
                error_label.update("API Key is required.")
                error_label.styles.display = "block"
                self.query_one("#api_key_input", Input).focus()
                return

        target_preset = preset_name or "Custom OpenAI"
        existing = self.presets.get(target_preset, {})
        default_model = existing.get("default_model") or "anthropic/claude-3.7-sonnet"
        result = {
            "preset_name": target_preset,
            "provider_type": "openai",
            "use_vertex_ai": False,
            "base_url": base_url,
            "api_key": api_key,
            "default_model": default_model,
        }
        if save:
            save_preset(target_preset, result, set_as_active=True)
        else:
            if target_preset in self.presets:
                set_active_preset(target_preset)
        self.dismiss(result)
