from textual.app import ComposeResult
from textual.widgets import Static, Button
from textual.containers import Horizontal

class PermissionBox(Static):
    """An inline safety box that renders directly inside the chat history."""
    
    def __init__(self, title: str, message: str, callback):
        # We give it the same base classes as a chat message, plus a specific alert class
        super().__init__(classes="message permission-msg") 
        self.title_text = title
        self.message_text = message
        self.callback = callback

    def compose(self) -> ComposeResult:
        # Display the warning text
        yield Static(f"[bold red]{self.title_text}[/bold red]\n[dim]{self.message_text}[/dim]")
        
        # Display the buttons side-by-side
        with Horizontal(id="perm-buttons"):
            yield Button("Yes, Allow", id="yes", variant="success")
            yield Button("No, Deny", id="no", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Fires when the user clicks Yes or No."""
        # 1. Remove the buttons so the chat history looks clean!
        self.query_one("#perm-buttons").remove()
        
        # 2. Update the box to show what the user chose
        if event.button.id == "yes":
            self.mount(Static("[bold green]✔ Permission Granted[/bold green]"))
            self.callback(True)
        else:
            self.mount(Static("[bold red]✖ Permission Denied[/bold red]"))
            self.callback(False)
        self.remove()

