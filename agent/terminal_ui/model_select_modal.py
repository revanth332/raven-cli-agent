from __future__ import annotations

from typing import List, Dict, Any, Optional
import threading

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import OptionList, Button, Static, Input
from textual.widgets.option_list import Option
from textual.containers import Vertical, Horizontal
from textual import work

from agent.core.settings import settings
from agent.core.vision import is_model_vision_capable
from agent.core.preset_manager import get_active_preset, add_preset_model
from agent.core.model_fetcher import fetch_models


class ModelSelectModal(ModalScreen[str]):
    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    CSS = """
    ModelSelectModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #modal_container {
        width: 76;
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

    #search_input {
        margin-bottom: 1;
        background: #121212;
        border: round #334155;
        color: #F8FAFC;
    }

    #model_list {
        height: 12;
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
        border: round #334155;
        color: #F8FAFC;
    }

    #status_label {
        color: #94A3B8;
        margin-bottom: 1;
        text-align: center;
    }

    #button_container {
        height: auto;
        align: right middle;
    }

    Button {
        margin-left: 1;
        min-width: 12;
        height: 3;
        padding: 0 1;
    }

    #refresh_btn {
        background: #1e293b;
        color: #38BDF8;
        border: round #0284C7;
    }

    #cancel_btn {
        background: transparent;
        color: #E2E8F0;
        border: round #64748B;
    }

    #select_btn {
        color: #FFFFFF;
        border: round #10B981;
        text-style: bold;
    }
    """

    def __init__(self, current_model: Optional[str] = None) -> None:
        super().__init__()
        self.preset_name, self.preset_cfg = get_active_preset()
        self.current_model = current_model or getattr(settings, "RAVEN_MODEL", "") or self.preset_cfg.get("default_model", "")
        self.favorite_model_ids: List[str] = self.preset_cfg.get("models", [])
        self.all_models: List[Dict[str, Any]] = []
        self.filtered_models: List[Dict[str, Any]] = []
        self._is_fetching = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Static(f"Select AI Model ({self.preset_name})", id="modal_title")
            yield Input(placeholder="Search models...", id="search_input")
            yield OptionList(id="model_list")
            yield Input(placeholder="Or type custom model string...", id="custom_input")
            yield Static("Loading models...", id="status_label")
            
            with Horizontal(id="button_container"):
                yield Button("Refresh", id="refresh_btn")
                yield Button("Cancel", id="cancel_btn")
                yield Button("Select", id="select_btn")

    def on_mount(self) -> None:
        self._load_models_initial()

    def _load_models_initial(self) -> None:
        """Loads cached models and kicks off background sync if empty."""
        cached_or_favorites = fetch_models(self.preset_name, self.preset_cfg, force_refresh=False)
        self._populate_model_data(cached_or_favorites)
        self.update_option_list()

        # If cache only had default preset fallbacks, trigger async discovery refresh in background
        if len(self.all_models) <= len(self.favorite_model_ids):
            self.action_refresh_models()

    def _populate_model_data(self, model_list: List[Dict[str, Any]]) -> None:
        fav_set = set(self.favorite_model_ids)
        combined: List[Dict[str, Any]] = []
        seen_ids = set()

        # 1. Add current model if present
        if self.current_model and self.current_model not in seen_ids:
            seen_ids.add(self.current_model)
            combined.append({
                "id": self.current_model,
                "name": self.current_model,
                "is_favorite": True,
                "vision": is_model_vision_capable(self.current_model),
            })

        # 2. Add preset favorite models
        for fid in self.favorite_model_ids:
            if fid not in seen_ids:
                seen_ids.add(fid)
                combined.append({
                    "id": fid,
                    "name": fid,
                    "is_favorite": True,
                    "vision": is_model_vision_capable(fid),
                })

        # 3. Add discovered models
        for m in model_list:
            mid = m.get("id")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                m_copy = dict(m)
                m_copy["is_favorite"] = mid in fav_set
                combined.append(m_copy)

        self.all_models = combined
        self.filtered_models = list(self.all_models)

    def update_option_list(self, query: str = "") -> None:
        query = query.lower().strip()
        if query:
            self.filtered_models = [
                m for m in self.all_models
                if query in m.get("id", "").lower() or query in m.get("name", "").lower()
            ]
        else:
            self.filtered_models = list(self.all_models)

        ol = self.query_one("#model_list", OptionList)
        ol.clear_options()

        status = self.query_one("#status_label", Static)
        status.update(f"Showing {len(self.filtered_models)} model(s) for {self.preset_name}")

        highlight_idx = 0
        for idx, m in enumerate(self.filtered_models):
            mid = m.get("id", "")
            is_fav = m.get("is_favorite", False)
            vision_capable = m.get("vision") or is_model_vision_capable(mid)

            type_badge = "[dim green][Vision][/dim green]" if vision_capable else "[dim #64748B][Text][/dim #64748B]"
            fav_badge = "[yellow]★[/yellow] " if is_fav else "  "
            
            prompt_text = f"{fav_badge}• {mid}  {type_badge}"
            if mid == self.current_model:
                prompt_text += "  [bold #06B6D4][active][/bold #06B6D4]"
                highlight_idx = idx

            ol.add_option(Option(prompt_text, id=mid))

        if self.filtered_models and highlight_idx < len(self.filtered_models):
            ol.highlighted = highlight_idx

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search_input":
            self.update_option_list(event.value)

    @work(exclusive=True, thread=True)
    def action_refresh_models(self) -> None:
        if self._is_fetching:
            return
        self._is_fetching = True
        try:
            self.app.call_from_thread(self._set_status_text, "Discovering models live from provider...")
            fresh_models = fetch_models(self.preset_name, self.preset_cfg, force_refresh=True)
            self.app.call_from_thread(self._on_refresh_completed, fresh_models)
        except Exception as e:
            self.app.call_from_thread(self._set_status_text, f"Discovery failed: {e}")
        finally:
            self._is_fetching = False

    def _set_status_text(self, text: str) -> None:
        status = self.query_one("#status_label", Static)
        status.update(text)

    def _on_refresh_completed(self, fresh_models: List[Dict[str, Any]]) -> None:
        self._populate_model_data(fresh_models)
        search_val = self.query_one("#search_input", Input).value
        self.update_option_list(search_val)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "select_btn":
            self.confirm_selection()
        elif event.button.id == "refresh_btn":
            self.action_refresh_models()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id:
            self._save_and_dismiss(option_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "custom_input":
            val = event.value.strip()
            if val:
                self._save_and_dismiss(val)
            else:
                self.confirm_selection()
        elif event.input.id == "search_input":
            self.confirm_selection()

    def confirm_selection(self) -> None:
        custom_val = self.query_one("#custom_input", Input).value.strip()
        if custom_val:
            self._save_and_dismiss(custom_val)
            return

        ol = self.query_one("#model_list", OptionList)
        if ol.highlighted is not None and ol.highlighted < len(self.filtered_models):
            selected_model = self.filtered_models[ol.highlighted].get("id")
            if selected_model:
                self._save_and_dismiss(selected_model)
                return

        self.dismiss(None)

    def _save_and_dismiss(self, model_id: str) -> None:
        # Save as a known model for this preset so it stays available
        try:
            add_preset_model(self.preset_name, model_id)
        except Exception:
            pass
        self.dismiss(model_id)
