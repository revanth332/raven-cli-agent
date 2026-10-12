"""
Modal screen for viewing, restoring, or deleting saved checkpoints in Textual TUI.
"""

from typing import Optional, Tuple
from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import OptionList, Input, Static, Button
from textual.widgets.option_list import Option

from agent.tools.checkpoint_tools import get_project_checkpoints, delete_checkpoint


class CheckpointSelectModal(ModalScreen[tuple | None]):
    """
    Interactive modal popup displaying all stored checkpoints with auto-search filtering.
    Returns ('restore', checkpoint_id) or None if dismissed.
    """

    CSS_PATH = "styles/checkpoint_modal.tcss"

    def compose(self) -> ComposeResult:
        with Vertical(id="checkpoint_modal_container"):
            yield Static("PROJECT CHECKPOINTS", id="checkpoint_modal_title")
            yield Input(placeholder="Search checkpoints... (↑/↓ to navigate, Enter to restore, Del to delete)", id="checkpoint_search_input")
            yield OptionList(id="checkpoint_option_list")
            with Horizontal(id="checkpoint_modal_actions"):
                yield Button("Restore", id="btn_restore")
                yield Button("Delete", id="btn_delete")
                yield Button("Cancel", id="btn_cancel")

    def on_mount(self) -> None:
        self.all_checkpoints = get_project_checkpoints()
        self.populate_options(self.all_checkpoints)
        self.query_one("#checkpoint_search_input", Input).focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def populate_options(self, checkpoints, target_highlight: int = 0) -> None:
        opt_list = self.query_one("#checkpoint_option_list", OptionList)
        opt_list.clear_options()

        if not checkpoints:
            opt_list.add_option(Option("[#94A3B8]No checkpoints found for this project.[/#94A3B8]", id="none"))
            return

        for ckpt in checkpoints:
            cid = ckpt.get("checkpoint_id", "unknown")
            cname = ckpt.get("checkpoint_name", "unnamed")
            ts = ckpt.get("timestamp", "unknown")
            files_count = ckpt.get("total_files", 0)

            file_label = f"{files_count} file(s)" if files_count else "clean working tree"
            label = (
                f"[bold cyan]{cname}[/bold cyan] [dim]({cid})[/dim]\n"
                f" │ [dim]Saved:[/dim] {ts}  │  [dim]Files:[/dim] {file_label}"
            )
            opt_list.add_option(Option(label, id=cid))

        if checkpoints:
            safe_index = max(0, min(target_highlight, len(checkpoints) - 1))
            opt_list.highlighted = safe_index

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        if not query:
            self.populate_options(self.all_checkpoints)
            return

        filtered = [
            c for c in self.all_checkpoints
            if query in c.get("checkpoint_name", "").lower()
            or query in c.get("checkpoint_id", "").lower()
            or query in c.get("timestamp", "").lower()
        ]
        self.populate_options(filtered)

    def on_key(self, event: events.Key) -> None:
        search_input = self.query_one("#checkpoint_search_input", Input)
        opt_list = self.query_one("#checkpoint_option_list", OptionList)

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
        elif event.key == "enter":
            btn_delete = self.query_one("#btn_delete", Button)
            btn_cancel = self.query_one("#btn_cancel", Button)
            btn_restore = self.query_one("#btn_restore", Button)
            if not btn_cancel.has_focus and not btn_delete.has_focus and not btn_restore.has_focus:
                self.restore_highlighted_checkpoint()
                event.prevent_default()
                event.stop()
        elif event.key in ["delete", "ctrl+d"]:
            self.delete_highlighted_checkpoint()
            event.prevent_default()
            event.stop()
        elif event.key == "escape":
            self.dismiss(None)
            event.prevent_default()
            event.stop()

    def restore_highlighted_checkpoint(self) -> None:
        opt_list = self.query_one("#checkpoint_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return

        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.id == "none":
            return

        self.dismiss(("restore", str(opt.id)))

    def delete_highlighted_checkpoint(self) -> None:
        opt_list = self.query_one("#checkpoint_option_list", OptionList)
        if opt_list.highlighted is None or opt_list.option_count == 0:
            return

        opt = opt_list.get_option_at_index(opt_list.highlighted)
        if not opt or not opt.id or opt.id == "none":
            return

        current_idx = opt_list.highlighted
        checkpoint_id = str(opt.id)
        if delete_checkpoint(checkpoint_id):
            self.all_checkpoints = get_project_checkpoints()
            search_input = self.query_one("#checkpoint_search_input", Input)
            query = search_input.value.strip().lower()
            if query:
                filtered = [
                    c for c in self.all_checkpoints
                    if query in c.get("checkpoint_name", "").lower()
                    or query in c.get("checkpoint_id", "").lower()
                    or query in c.get("timestamp", "").lower()
                ]
                self.populate_options(filtered, target_highlight=current_idx)
            else:
                self.populate_options(self.all_checkpoints, target_highlight=current_idx)

        # Restore focus back to search input
        self.query_one("#checkpoint_search_input", Input).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id and event.option.id != "none":
            self.dismiss(("restore", str(event.option.id)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_delete":
            self.delete_highlighted_checkpoint()
        elif event.button.id == "btn_restore":
            self.restore_highlighted_checkpoint()
