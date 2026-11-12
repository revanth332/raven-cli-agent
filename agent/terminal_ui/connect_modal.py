from typing import Optional, Dict, Any, List
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Input, Label, OptionList, RadioSet, RadioButton
from textual.widgets.option_list import Option
from textual.containers import Vertical, Horizontal

from agent.core.preset_manager import (
    load_presets,
    save_preset,
    delete_preset,
    get_active_preset,
    set_active_preset,
    BUILTIN_PRESETS,
)


def is_preset_configured(preset_name: str, cfg: Dict[str, Any]) -> bool:
    """Checks whether a preset has all required configuration fields to connect directly."""
    provider_type = cfg.get("provider_type", "openai")
    is_vertex = bool(cfg.get("use_vertex_ai") or provider_type == "vertex")
    if is_vertex:
        return True

    base_url = (cfg.get("base_url") or "").strip()
    api_key = (cfg.get("api_key") or "").strip()

    if not base_url:
        return False

    if any(loc in base_url.lower() for loc in ["localhost", "127.0.0.1", "ollama", ":11434"]):
        return True

    if not api_key:
        return False

    return True


class PresetFormModal(ModalScreen[Optional[Dict[str, Any]]]):
    """
    Modal screen for creating a new provider preset or editing an existing preset.
    Locks Preset Name and Provider Type when editing built-in presets.
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", priority=True),
    ]
    CSS_PATH = "styles/connect_modal.tcss"

    def __init__(
        self,
        preset_name: Optional[str] = None,
        preset_cfg: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.preset_name = preset_name
        self.preset_cfg = dict(preset_cfg) if preset_cfg else {}
        self.is_editing = bool(preset_name)
        self.is_builtin = bool(preset_name and preset_name in BUILTIN_PRESETS)
        self.presets = load_presets().get("presets", {})

    def compose(self) -> ComposeResult:
        is_vertex = bool(
            self.preset_cfg.get("use_vertex_ai") or self.preset_cfg.get("provider_type") == "vertex"
        )
        base_url = self.preset_cfg.get("base_url") or ""
        api_key = "" if is_vertex else (self.preset_cfg.get("api_key") or "")
        name_val = self.preset_name or ""
        title_text = f"Edit Preset: {self.preset_name}" if self.is_editing else "New Provider Preset"

        with Vertical(id="preset_form_container"):
            with Horizontal(id="preset_form_header_row"):
                yield Static(title_text, id="preset_form_title")
                yield Static("esc to cancel", id="preset_form_close_hint")

            yield Label("Provider Type:", classes="field_label")
            with RadioSet(id="provider_type_radios", disabled=self.is_builtin):
                yield RadioButton("OpenAI-Compatible Endpoint", id="radio_openai", value=not is_vertex)
                yield RadioButton("Google Vertex AI", id="radio_vertex", value=is_vertex)

            yield Label("Preset Name:", classes="field_label")
            yield Input(
                value=name_val,
                placeholder="Enter preset name",
                id="preset_name_input",
                classes="field_input",
                disabled=self.is_builtin,
            )

            yield Label("Base URL:", classes="field_label", id="base_url_label")
            yield Input(
                value=base_url,
                placeholder=(
                    "Optional custom OpenAPI endpoint or leave blank for default"
                    if is_vertex
                    else "e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1"
                ),
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

            yield Static("", id="form_error_label")

            with Horizontal(id="form_button_container"):
                yield Button("Cancel", id="cancel_btn")
                yield Button("Save & Connect", id="submit_btn")

    def on_mount(self) -> None:
        name_input = self.query_one("#preset_name_input", Input)
        base_url_input = self.query_one("#base_url_input", Input)
        api_key_input = self.query_one("#api_key_input", Input)

        if not self.is_editing or not name_input.value.strip():
            name_input.focus()
        elif not base_url_input.value.strip() and not base_url_input.disabled:
            base_url_input.focus()
        elif not api_key_input.disabled and not api_key_input.value.strip():
            api_key_input.focus()
        else:
            base_url_input.focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.action_dismiss_modal()
            event.prevent_default()
            event.stop()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "provider_type_radios":
            return
        is_vertex = event.pressed.id == "radio_vertex"
        base_url_input = self.query_one("#base_url_input", Input)
        api_key_input = self.query_one("#api_key_input", Input)
        error_label = self.query_one("#form_error_label", Static)
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "submit_btn":
            self.submit_form()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "preset_name_input":
            base_url = self.query_one("#base_url_input", Input)
            if not base_url.disabled:
                base_url.focus()
            else:
                self.submit_form()
        elif event.input.id == "base_url_input":
            api_key = self.query_one("#api_key_input", Input)
            if not api_key.disabled:
                api_key.focus()
            else:
                self.submit_form()
        else:
            self.submit_form()

    def submit_form(self) -> None:
        is_vertex = self.query_one("#radio_vertex", RadioButton).value
        preset_name = self.query_one("#preset_name_input", Input).value.strip()
        if self.is_builtin and self.preset_name:
            preset_name = self.preset_name

        base_url = self.query_one("#base_url_input", Input).value.strip()
        api_key = self.query_one("#api_key_input", Input).value.strip()
        error_label = self.query_one("#form_error_label", Static)

        if not preset_name:
            error_label.update("Preset name is required.")
            error_label.styles.display = "block"
            self.query_one("#preset_name_input", Input).focus()
            return

        if not self.is_editing:
            if preset_name in self.presets or preset_name in BUILTIN_PRESETS:
                error_label.update(f"Preset '{preset_name}' already exists.")
                error_label.styles.display = "block"
                self.query_one("#preset_name_input", Input).focus()
                return
        else:
            if not self.is_builtin and self.preset_name and preset_name != self.preset_name:
                if preset_name in BUILTIN_PRESETS:
                    error_label.update(f"Cannot overwrite built-in preset '{preset_name}'.")
                    error_label.styles.display = "block"
                    self.query_one("#preset_name_input", Input).focus()
                    return
                if preset_name in self.presets:
                    error_label.update(f"Preset '{preset_name}' already exists.")
                    error_label.styles.display = "block"
                    self.query_one("#preset_name_input", Input).focus()
                    return

        if is_vertex:
            existing = self.presets.get(self.preset_name or preset_name, {})
            default_model = existing.get("default_model") or "google/gemini-2.5-flash"
            result = {
                "preset_name": preset_name,
                "provider_type": "vertex",
                "use_vertex_ai": True,
                "base_url": base_url or None,
                "api_key": None,
                "default_model": default_model,
                "models": existing.get("models", []),
                "image_models": existing.get("image_models", []),
                "default_image_model": existing.get("default_image_model", ""),
            }
            if self.is_editing and not self.is_builtin and self.preset_name and preset_name != self.preset_name:
                try:
                    delete_preset(self.preset_name)
                except Exception:
                    pass
            try:
                save_preset(preset_name, result, set_as_active=False)
            except Exception as e:
                error_label.update(str(e))
                error_label.styles.display = "block"
                return
            self.dismiss(result)
            return

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

        existing = self.presets.get(self.preset_name or preset_name, {})
        default_model = existing.get("default_model") or "anthropic/claude-3.7-sonnet"
        result = {
            "preset_name": preset_name,
            "provider_type": "openai",
            "use_vertex_ai": False,
            "base_url": base_url,
            "api_key": api_key,
            "default_model": default_model,
            "models": existing.get("models", []),
            "image_models": existing.get("image_models", []),
            "default_image_model": existing.get("default_image_model", ""),
        }
        if self.is_editing and not self.is_builtin and self.preset_name and preset_name != self.preset_name:
            try:
                delete_preset(self.preset_name)
            except Exception:
                pass
        try:
            save_preset(preset_name, result, set_as_active=False)
        except Exception as e:
            error_label.update(str(e))
            error_label.styles.display = "block"
            return

        self.dismiss(result)


class ConnectModal(ModalScreen[Optional[Dict[str, Any]]]):
    """
    Searchable provider preset selection modal (modeled after SessionSelectModal).
    Supports selecting (Enter), creating (ctrl+n), updating (ctrl+u), and deleting (ctrl+d) presets.
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", priority=True),
    ]
    CSS_PATH = "styles/connect_modal.tcss"

    def __init__(
        self,
        initial_preset: Optional[str] = None,
        title: str = "Provider Presets",
        active_preset_override: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.initial_preset = initial_preset
        self.modal_title = title
        self.active_preset_override = active_preset_override
        self.presets: Dict[str, Dict[str, Any]] = {}
        self.active_preset_name: str = ""
        self._filtered_preset_keys: List[str] = []

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="preset_modal_container"):
            with Horizontal(id="preset_header_row"):
                yield Static(self.modal_title, id="preset_modal_title")
                yield Static("esc", id="preset_close_hint")

            yield Input(
                placeholder="Search presets...",
                id="preset_search_input",
            )

            yield OptionList(id="preset_option_list")

            yield Static(
                "select [dim #71717a]enter[/dim #71717a]    "
                "new [dim #71717a]ctrl+n[/dim #71717a]    "
                "edit [dim #71717a]ctrl+u[/dim #71717a]    "
                "delete [dim #71717a]ctrl+d[/dim #71717a]",
                id="preset_footer_shortcuts",
            )

    def on_mount(self) -> None:
        self._load_presets_data()
        target = self.initial_preset if (self.initial_preset and self.initial_preset in self.presets) else self.active_preset_name
        self.populate_options(target_preset=target)
        self.query_one("#preset_search_input", Input).focus()

    def _load_presets_data(self) -> None:
        data = load_presets()
        self.presets = data.get("presets", {})
        if self.active_preset_override and self.active_preset_override in self.presets:
            self.active_preset_name = self.active_preset_override
        else:
            self.active_preset_name, _ = get_active_preset()

    def populate_options(self, filter_query: str = "", target_preset: Optional[str] = None) -> None:
        opt_list = self.query_one("#preset_option_list", OptionList)
        opt_list.clear_options()

        query = filter_query.strip().lower()
        matching_keys: List[str] = []
        for name, cfg in self.presets.items():
            if not query:
                matching_keys.append(name)
            else:
                ptype = cfg.get("provider_type", "openai").lower()
                base_url = (cfg.get("base_url") or "").lower()
                default_m = (cfg.get("default_model") or "").lower()
                if (
                    query in name.lower()
                    or query in ptype
                    or query in base_url
                    or query in default_m
                ):
                    matching_keys.append(name)

        self._filtered_preset_keys = matching_keys

        opt_list.add_option(
            Option("[bold #10B981]Presets[/bold #10B981]", disabled=True, id="header_presets")
        )

        target_highlight_idx = None
        first_valid_idx = None

        for name in matching_keys:
            curr_idx = opt_list.option_count
            opt_list.add_option(Option(name, id=name))

            if first_valid_idx is None:
                first_valid_idx = curr_idx

            if target_preset and name == target_preset:
                target_highlight_idx = curr_idx

        new_idx = opt_list.option_count
        opt_list.add_option(
            Option("[bold #10B981]+ New Custom Preset[/bold #10B981]", id="__new__")
        )
        if first_valid_idx is None:
            first_valid_idx = new_idx

        if target_preset == "__new__":
            target_highlight_idx = new_idx

        if target_highlight_idx is not None:
            opt_list.highlighted = target_highlight_idx
        elif first_valid_idx is not None:
            opt_list.highlighted = first_valid_idx

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "preset_search_input":
            self.populate_options(filter_query=event.value)

    def on_key(self, event: events.Key) -> None:
        opt_list = self.query_one("#preset_option_list", OptionList)

        if event.key == "down":
            opt_list.action_cursor_down()
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            opt_list.action_cursor_up()
            event.prevent_default()
            event.stop()
        elif event.key in ["page_down", "pagedown"]:
            opt_list.action_page_down()
            event.prevent_default()
            event.stop()
        elif event.key in ["page_up", "pageup"]:
            opt_list.action_page_up()
            event.prevent_default()
            event.stop()
        elif event.key == "escape":
            self.action_dismiss_modal()
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+n":
            self.create_new_preset()
            event.prevent_default()
            event.stop()
        elif event.key == "ctrl+u":
            self.update_highlighted_preset()
            event.prevent_default()
            event.stop()
        elif event.key in ["delete", "ctrl+d"]:
            self.delete_highlighted_preset()
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            self.select_highlighted_preset()
            event.prevent_default()
            event.stop()

    def select_highlighted_preset(self) -> None:
        opt_list = self.query_one("#preset_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return
        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.disabled or opt.id in ("none", "header_presets"):
            return

        preset_key = str(opt.id)
        if preset_key == "__new__":
            self.create_new_preset()
            return

        cfg = self.presets.get(preset_key, {})
        if not is_preset_configured(preset_key, cfg):
            self.update_preset(preset_key)
            return

        conn_data = {
            "preset_name": preset_key,
            "provider_type": cfg.get("provider_type", "openai"),
            "use_vertex_ai": bool(cfg.get("use_vertex_ai") or cfg.get("provider_type") == "vertex"),
            "base_url": cfg.get("base_url"),
            "api_key": cfg.get("api_key"),
            "default_model": cfg.get("default_model"),
            "models": cfg.get("models", []),
            "image_models": cfg.get("image_models", []),
            "default_image_model": cfg.get("default_image_model", ""),
        }
        self.dismiss(conn_data)

    def update_highlighted_preset(self) -> None:
        opt_list = self.query_one("#preset_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return
        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.disabled or opt.id in ("none", "header_presets"):
            return

        preset_key = str(opt.id)
        if preset_key == "__new__":
            self.create_new_preset()
        else:
            self.update_preset(preset_key)

    def update_preset(self, preset_key: str) -> None:
        cfg = self.presets.get(preset_key, {})
        self._open_form_modal(preset_name=preset_key, preset_cfg=cfg)

    def create_new_preset(self) -> None:
        self._open_form_modal(preset_name=None, preset_cfg=None)

    def _open_form_modal(
        self, preset_name: Optional[str], preset_cfg: Optional[Dict[str, Any]]
    ) -> None:
        def on_form_dismiss(conn_data: Optional[Dict[str, Any]]) -> None:
            if conn_data:
                self.dismiss(conn_data)
            else:
                self._load_presets_data()
                search_inp = self.query_one("#preset_search_input", Input)
                self.populate_options(
                    filter_query=search_inp.value,
                    target_preset=preset_name or self.active_preset_name,
                )
                search_inp.focus()

        self.app.push_screen(
            PresetFormModal(preset_name=preset_name, preset_cfg=preset_cfg),
            on_form_dismiss,
        )

    def delete_highlighted_preset(self) -> None:
        opt_list = self.query_one("#preset_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return
        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.disabled or opt.id in ("none", "header_presets", "__new__"):
            return

        preset_key = str(opt.id)
        if preset_key in BUILTIN_PRESETS:
            self.notify(
                f"Cannot delete built-in preset '{preset_key}'",
                title="Built-in Preset",
                severity="warning",
            )
            return

        try:
            delete_preset(preset_key)
            self.notify(
                f"Deleted preset '{preset_key}'",
                title="Preset Deleted",
                severity="information",
            )
            self._load_presets_data()
            search_inp = self.query_one("#preset_search_input", Input)
            self.populate_options(
                filter_query=search_inp.value,
                target_preset=self.active_preset_name,
            )
        except Exception as e:
            self.notify(str(e), title="Error", severity="error")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if (
            event.option.id
            and not event.option.disabled
            and event.option.id not in ("none", "header_presets")
        ):
            self.select_highlighted_preset()


PresetSelectModal = ConnectModal

