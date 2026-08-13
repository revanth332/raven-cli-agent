from textual.app import ComposeResult
from textual.widgets import Static, Button
from textual.containers import Horizontal

class PermissionBar(Static):
    """A safety prompt bar mounted above the chat input during tool execution requests."""
    
    def __init__(self, title: str, message: str, on_allow, on_deny):
        super().__init__(id="permission_bar")
        self.title_text = title
        self.message_text = message
        self.on_allow = on_allow
        self.on_deny = on_deny

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #EF4048]{self.title_text}[/bold #EF4048]\n"
            f"[dim #E2E8F0]{self.message_text}[/dim #E2E8F0]\n"
            f"[dim #38BDF8]Press [bold]Enter[/bold] to Allow, or type an optional instruction below and press Enter to deny with feedback.[/dim #38BDF8]"
        )
        with Horizontal(id="perm-buttons"):
            yield Button("Allow (Enter)", id="yes")
            yield Button("Deny (Esc)", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button clicks for Allow and Deny."""
        if event.button.id == "yes":
            self.on_allow()
        else:
            self.on_deny()


# Backward compatibility alias
PermissionBox = PermissionBar


