from __future__ import annotations

from typing import List, Dict, Any, Optional
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static, Input
from textual.widgets.option_list import Option
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual import events

from agent.core.settings import settings
from agent.core.preset_manager import (
    load_presets,
    get_image_preset,
    set_image_preset,
    get_preset_image_models,
    add_preset_image_model,
    remove_preset_image_model,
)


class ImageModelSelectModal(ModalScreen[Optional[Dict[str, str]]]):
    """
    Modal for selecting an Image Generation Model for a chosen Provider Preset.
    Pressing Esc dismisses with None so the caller can navigate back to PresetSelectModal.
    """
    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", priority=True),
        Binding("ctrl+d", "delete_selected_model", "Delete Model", priority=True),
    ]
    CSS_PATH = "styles/image_model_select_modal.tcss"

    def __init__(
        self,
        current_model: Optional[str] = None,
        preset_name: Optional[str] = None,
        preset_cfg: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__()
        data = load_presets()
        self.presets: Dict[str, Any] = data.get("presets", {})
        self.provider_names: List[str] = list(self.presets.keys())

        # Resolve active image preset
        active_img_preset, active_cfg = get_image_preset()
        custom_provider = (getattr(settings, "IMAGE_PROVIDER", None) or "").strip()
        if custom_provider and custom_provider in self.presets:
            active_img_preset = custom_provider
            active_cfg = dict(self.presets[active_img_preset])

        self.active_image_provider = active_img_preset

        if preset_name and preset_name in self.presets:
            self.selected_provider = preset_name
            selected_cfg = preset_cfg or self.presets.get(preset_name, {})
        elif preset_name and preset_cfg is not None:
            self.selected_provider = preset_name
            selected_cfg = preset_cfg
        else:
            self.selected_provider = active_img_preset
            if self.selected_provider not in self.presets and self.provider_names:
                self.selected_provider = self.provider_names[0]
            selected_cfg = self.presets.get(self.selected_provider, active_cfg)

        # Resolve active image model
        configured_model = (getattr(settings, "IMAGE_MODEL", "") or active_cfg.get("default_image_model", "")).strip()
        self.active_image_model = configured_model or "gemini-3.1-flash-image"

        if current_model:
            self.current_model = current_model.strip()
        elif self.selected_provider == self.active_image_provider:
            self.current_model = self.active_image_model
        else:
            self.current_model = (
                selected_cfg.get("default_image_model")
                or (selected_cfg.get("image_models", [""])[0] if selected_cfg.get("image_models") else "")
            )

        self.all_models: List[str] = []
        self.filtered_models: List[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="image_modal_container"):
            with Horizontal(id="image_header_row"):
                yield Static(f"Select Image Model ({self.selected_provider})", id="image_modal_title")
                yield Static("esc to close", id="image_close_hint")
            yield Input(placeholder="Search image models...", id="search_input")
            yield OptionList(id="image_model_list")
            yield Input(placeholder="Or type custom image model string...", id="custom_input")
            yield Static("Ready", id="status_label")
            yield Static("select enter    delete ctrl+d    esc back", id="image_footer_shortcuts")

    def on_mount(self) -> None:
        self._load_provider_models()
        self.query_one("#search_input", Input).focus()

    def _load_provider_models(self) -> None:
        models = get_preset_image_models(self.selected_provider)
        preset_cfg = self.presets.get(self.selected_provider, {})
        default_im = preset_cfg.get("default_image_model", "")

        combined: List[str] = []
        seen = set()

        # 1. Include active_image_model only if viewing the active_image_provider
        if self.selected_provider == self.active_image_provider and self.active_image_model:
            seen.add(self.active_image_model)
            combined.append(self.active_image_model)

        # 2. Preset default image model
        if default_im and default_im not in seen:
            seen.add(default_im)
            combined.append(default_im)

        # 3. Preset curated image models
        for m in models:
            if m and m not in seen:
                seen.add(m)
                combined.append(m)

        self.all_models = combined
        self.filtered_models = list(self.all_models)
        search_val = ""
        try:
            search_val = self.query_one("#search_input", Input).value
        except Exception:
            pass
        self.update_option_list(search_val)

    def update_option_list(self, query: str = "") -> None:
        query = query.lower().strip()
        if query:
            self.filtered_models = [m for m in self.all_models if query in m.lower()]
        else:
            self.filtered_models = list(self.all_models)

        ol = self.query_one("#image_model_list", OptionList)
        ol.clear_options()

        status = self.query_one("#status_label", Static)
        status.update(f"Showing {len(self.filtered_models)} image model(s) for {self.selected_provider}")

        if not self.filtered_models:
            ol.add_option(Option("[dim #71717a]No configured image models — type a custom model below[/dim #71717a]", id="__none__", disabled=True))
            return

        highlight_idx = 0
        for idx, mid in enumerate(self.filtered_models):
            is_active = (self.selected_provider == self.active_image_provider and mid == self.active_image_model)
            if is_active or mid == self.current_model:
                highlight_idx = idx

            tag = "  [bold #06B6D4][ACTIVE][/bold #06B6D4]" if is_active else ""
            ol.add_option(Option(f"{mid}{tag}", id=mid))

        if self.filtered_models and highlight_idx < len(self.filtered_models):
            ol.highlighted = highlight_idx

    def action_delete_selected_model(self) -> None:
        ol = self.query_one("#image_model_list", OptionList)
        if ol.highlighted is not None and 0 <= ol.highlighted < len(self.filtered_models):
            target = self.filtered_models[ol.highlighted]
            if remove_preset_image_model(self.selected_provider, target):
                data = load_presets()
                self.presets = data.get("presets", {})
                self._load_provider_models()
                self.query_one("#status_label", Static).update(f"Removed '{target}' from {self.selected_provider}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search_input":
            self.update_option_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "custom_input":
            val = event.value.strip()
            if val:
                add_preset_image_model(self.selected_provider, val)
                self._apply_and_dismiss(self.selected_provider, val)
        elif event.input.id == "search_input":
            self.confirm_selection()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id and event.option_id != "__none__":
            self._apply_and_dismiss(self.selected_provider, str(event.option_id))

    def confirm_selection(self) -> None:
        custom_val = self.query_one("#custom_input", Input).value.strip()
        if custom_val:
            add_preset_image_model(self.selected_provider, custom_val)
            self._apply_and_dismiss(self.selected_provider, custom_val)
            return

        ol = self.query_one("#image_model_list", OptionList)
        if ol.highlighted is not None and 0 <= ol.highlighted < len(self.filtered_models):
            selected = self.filtered_models[ol.highlighted]
            if selected:
                self._apply_and_dismiss(self.selected_provider, selected)
                return

        search_val = self.query_one("#search_input", Input).value.strip()
        if search_val:
            add_preset_image_model(self.selected_provider, search_val)
            self._apply_and_dismiss(self.selected_provider, search_val)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.action_dismiss_modal()
            event.prevent_default()
            event.stop()
            return

        if event.key == "ctrl+d":
            self.action_delete_selected_model()
            event.prevent_default()
            event.stop()
            return

        search_input = self.query_one("#search_input", Input)
        custom_input = self.query_one("#custom_input", Input)
        opt_list = self.query_one("#image_model_list", OptionList)

        if search_input.has_focus or opt_list.has_focus:
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
            elif event.key == "enter" and not custom_input.has_focus:
                self.confirm_selection()
                event.prevent_default()
                event.stop()

    def _apply_and_dismiss(self, provider_name: str, model_id: str) -> None:
        set_image_preset(provider_name, default_model=model_id)
        settings.set_config({
            "IMAGE_PROVIDER": provider_name,
            "IMAGE_MODEL": model_id,
        })
        self.dismiss({"preset_name": provider_name, "model": model_id})

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
