from textual.app import ComposeResult
from textual.widgets import Static, Button
from textual.containers import Horizontal

class PermissionBar(Static):
    """A safety prompt bar mounted above the chat input during tool execution requests or checkpoints."""
    
    def __init__(
        self,
        title: str,
        message: str,
        on_allow,
        on_deny,
        allow_label: str = "Allow (Enter)",
        deny_label: str = "Deny (Esc)",
        hint_text: str = "Press [bold]Enter[/bold] to Allow, or type an optional instruction below and press Enter to deny with feedback."
    ):
        super().__init__(id="permission_bar")
        self.title_text = title
        self.message_text = message
        self.on_allow = on_allow
        self.on_deny = on_deny
        self.allow_label = allow_label
        self.deny_label = deny_label
        self.hint_text = hint_text

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #EF4048]{self.title_text}[/bold #EF4048]\n"
            f"[dim #E2E8F0]{self.message_text}[/dim #E2E8F0]\n"
            f"[dim #38BDF8]{self.hint_text}[/dim #38BDF8]"
        )
        with Horizontal(id="perm-buttons"):
            yield Button(self.allow_label, id="yes")
            yield Button(self.deny_label, id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles button clicks for Allow and Deny."""
        if event.button.id == "yes":
            self.on_allow()
        else:
            self.on_deny()


# Backward compatibility alias
PermissionBox = PermissionBar


