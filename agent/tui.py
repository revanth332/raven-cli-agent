# agent/tui.py
from textual.app import App, ComposeResult
from textual.widgets import Footer, Input, Static, Button, Label
from textual.containers import VerticalScroll,Horizontal,Grid,Vertical
from textual.screen import ModalScreen
from rich.markdown import Markdown
from textual import work
from agent.llm import get_chat_session
from google.genai import types
import threading
from agent.main import TOOL_REGISTRY
import time
from rich.console import Group
from rich.text import Text

raven_logo = """
 ██████╗  █████╗ ██╗   ██╗███████╗███╗   ██╗
 ██╔══██╗██╔══██╗██║   ██║██╔════╝████╗  ██║
 ██████╔╝███████║██║   ██║█████╗  ██╔██╗ ██║
 ██╔══██╗██╔══██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║
 ██║  ██║██║  ██║ ╚████╔╝ ███████╗██║ ╚████║
 ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝
    """

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

class ThinkingMessage(Static):
    """A message bubble that shows a typewriter animation until updated."""
    FULL_TEXT = "Thinking..."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.char_index = 0
        self.direction = 1
        self._timer = None
        self._is_thinking = True

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self.tick)

    def tick(self) -> None:
        if not self._is_thinking:
            return
            
        self.char_index += self.direction
        if self.char_index >= len(self.FULL_TEXT):
            self.char_index = len(self.FULL_TEXT)
            self.direction = -1
        elif self.char_index <= 0:
            self.char_index = 0
            self.direction = 1
            
        super().update(f"● {self.FULL_TEXT[:self.char_index]}")

    def update(self, renderable="") -> None:
        if self._is_thinking:
            self._is_thinking = False
            if self._timer:
                self._timer.pause()
        super().update(renderable)

    def reset_thinking(self) -> None:
        """Resets the state back to thinking and restarts the typewriter animation."""
        self._is_thinking = True
        self.char_index = 0
        self.direction = 1
        if self._timer:
            self._timer.resume()
        super().update("● ")

class RavenTUI(App):
    # --- CLAUDE-STYLE CSS STYLING ---
    CSS = """
    Screen {
        color: #E2E8F0;      /* Crisp, bright off-white text */
    }
    
    Header {
        color: #090D16;      /* High-contrast dark text inside the header */
        text-style: bold;
        height: 3;           /* Makes the header slightly taller and cleaner */
        content-align: center middle;
    }
    Footer {
        background: #05070B; /* Sleek black footer */
        color: #64748B;      /* Dim keybind labels */
    }

    #welcome-container {
        align: center middle;
        height: auto;
    }

    .logo-text {
        width: auto;
        height: auto;
        content-align: center middle;
    }

    .version-text {
        width: auto;
        height: 100%;
        content-align: left middle;
        padding-left: 2;
    }

    #history {
        height: 1fr;
        padding: 1 2;
        background: transparent;
        overflow-y: scroll;
        scrollbar-size: 0 0;
    }
    
    .message {
        margin: 1 0;
        padding: 1 1;
        border-title-align: left;
    }
    
    .user-msg {
        color: #F1F5F9;
    }
    
    .raven-msg {
        color: #ECFDF5;
    }

    Input {
        border: solid #06B6D4; /* Brilliant double sky-blue border */
        margin: 1 1;
        padding: 0 1;
        color: #F8FAFC;         /* Bright text while typing */
        background: transparent;
    }
    .permission-msg {
        padding: 1 1;
        margin: 1 0;
    }
    
    #perm-buttons {
        height: auto;
        margin-top: 1;
    }
    
    #perm-buttons Button {
        margin-right: 2;
        min-width: 12;
        height: 3;
        background: transparent;
        border: none;
    }
    #perm-buttons Button:hover {
        background: rgba(255, 255, 255, 0.1);
    }
    #perm-buttons #yes {
        color: #ffffff;
        background: transparent;
        border: round #ffffff;
    }
    #perm-buttons #no {
        color: #ffffff;
        background: transparent;
        border: round #ffffff;
    }
    #thinking_container {
        height:auto;
        border: none;
        margin:0 1;
    }
    #bottom_bar {
        dock: bottom;
        height: auto;
    }
    """
    # Define system hotkeys for the footer
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Exit"),
    ]

    def on_mount(self):
        """Runs the exact moment the UI mounts to the screen."""
        self.chat_session = None

        self.permission_event = threading.Event()
        self.permission_result = False

        self.initialize_ai()

    def ask_permission_ui(self,title:str,message:str):
        """Pushes the modal to the screen and handles the result."""
        def callback(result:bool):
            self.permission_result = result
            self.permission_event.set()

        history = self.query_one("#history")
        box = PermissionBox(title, message, callback)
        history.mount(box)
        
        # Scroll down so the user immediately sees the buttons
        box.scroll_visible()
    
    @work(thread=True)
    def initialize_ai(self):
        """Background task to load credentials and initialize Gemini."""
        try:
            self.chat_session = get_chat_session()
            self.call_from_thread(self.notify, "Raven AI Engine initialized!", title="System", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Error initializing AI: {e}", title="Error", severity="error")

    def compose(self) -> ComposeResult:
        """Assembles the physical widgets on the screen."""
        # VerticalScroll acts as our scrollable conversation container
        from agent.utils import get_active_llm_model
        from pathlib import Path
        active_model = get_active_llm_model()
        current_project = Path.cwd().name
        
        with VerticalScroll(id="history") as history:
            # Add a welcome card on boot
            yield Horizontal(
                Static(f"[bold #06B6D4]{raven_logo}[/bold #06B6D4]", classes="logo-text"),
                Static(
                    f"[bold #06B6D4]RAVEN CLI AGENT v1.0.0[/bold #06B6D4]\n"
                    f"[dim]Ready to assist. Type below to begin.[/dim]\n\n"
                    f"[bold #06B6D4]Active Model:[/bold #06B6D4] {active_model}\n"
                    f"[bold #06B6D4]Current Project:[/bold #06B6D4] {current_project}\n"
                    f"[bold #06B6D4]Agent Version:[/bold #06B6D4] 1.0.0 (Raven Personal AI Developer Agent)",
                    classes="version-text"
                ),
                id="welcome-container"
            )
        # Create a single docked container at the bottom
        with Vertical(id="bottom_bar"):
            yield Horizontal(id="thinking_container")
            yield Input(placeholder="Ask Raven something... (Type 'exit' to quit)")
            yield Footer()

    # --- EVENT HANDLERS ---
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Triggers when the user presses 'Enter' in the input box."""
        user_input = event.value.strip()
        
        if not user_input:
            return
            
        if user_input.lower() in ["exit", "quit"]:
            self.exit()
            return

        # Clear the input box immediately for the next question
        input_widget = event.input
        input_widget.value = ""

        # 1. Echo the user's message into the scrollable history area
        history_container = self.query_one("#history")
        
        user_card = Static(classes="message user-msg")
        user_card.border_title = "User"
        user_card.styles.border = ("round", "#06B6D4")
        user_card.update(Markdown(user_input))
        history_container.mount(user_card)

        # 2. Echo a mock response from Raven for now
        raven_card = Static()
        history_container.mount(raven_card)
        raven_card.scroll_visible()

        self.stream_response(user_input,raven_card)
        
    
    @work(thread=True)
    def stream_response(self,query:str,raven_card:Static):
        """Background thread that streams the AI response without freezing the UI."""
        if not self.chat_session:
            self.call_from_thread(raven_card.update, "[red]AI is still initializing. Please try again.[/red]")
            return
        start_time = time.time()
        try:
            thinking_container = self.query_one("#thinking_container")
            text_response = ""
            tool_logs = Text()
            while True:
                function_calls = []
                max_retries = 5
                thinking_message = ThinkingMessage("")
                for attempt in range(max_retries):
                    try:
                        self.call_from_thread(thinking_container.mount,thinking_message)
                        generator = self.chat_session.send_message_stream(query)
                        for chunk in generator:

                            if hasattr(chunk,"function_calls") and chunk.function_calls:
                                function_calls.extend(chunk.function_calls)
                                continue
                            if hasattr(chunk,"text") and chunk.text:
                                text_response += chunk.text
                                if tool_logs:
                                    self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                                else:
                                    self.call_from_thread(raven_card.update, Markdown(text_response))
                                self.call_from_thread(raven_card.scroll_visible)
                        break
                    except Exception as api_error:
                        if thinking_message:                                                                                                                                
                            self.call_from_thread(thinking_message.remove)
                        error_str = str(api_error).lower()
                        if "429" in error_str or "exhausted" in error_str or "quota" in error_str:
                            if attempt < max_retries - 1:
                                # Exponential backoff: 2, 4, 8, 16 seconds...
                                sleep_time = 2 ** (attempt + 1) 
                                msg = f"⏳ *API Rate Limit hit. (Retrying in {sleep_time}s)*"
                                self.call_from_thread(raven_card.update, Markdown(msg))
                                time.sleep(sleep_time)
                                continue
                            raise api_error
                if thinking_message:
                    self.call_from_thread(thinking_message.remove)

                if len(function_calls) == 0:
                    break

                tool_responses = []
                for fc in function_calls:
                    tool_name = fc.name
                    tool_args = fc.args

                    if tool_name in TOOL_REGISTRY:
                        tool_meta = TOOL_REGISTRY[tool_name]
                        
                        if tool_name in ["execute_command", "run_ui_test"]:
                            self.permission_event.clear()
                            title = f"Action Required: {tool_name}"
                            msg = f"Raven wants to execute {tool_name}.\nArgs: {str(tool_args)[:100]}"

                            self.call_from_thread(self.ask_permission_ui,title,msg)
                            self.permission_event.wait()

                            if not self.permission_result:
                                result = "Error: User denied permission."
                                tool_responses.append(types.Part.from_function_response(name=tool_name, response={"result": result}))
                                continue
                            tool_logs.append(f"\n• {tool_name}")
                            tool_logs.append(f"({str(tool_args)[:100]})\n",style="dim white")
                            if text_response:
                                self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                            else:
                                self.call_from_thread(raven_card.update, tool_logs)
                            self.call_from_thread(raven_card.scroll_visible)

                        if tool_name == "patch_file":
                            file_path = tool_args.get("file_path", "Unknown")
                            search_block = tool_args.get("search_block", "")
                            replace_block = tool_args.get("replace_block", "")
                            
                            tool_logs.append(f"\n• Update")
                            tool_logs.append(f"({file_path})\n",style="dim white")
                            if search_block or replace_block:
                                search_block_lines = search_block.rstrip().split("\n")
                                replace_block_lines = replace_block.rstrip().split("\n")
                                tool_logs.append("   |_ Updated ",style="dim white")
                                tool_logs.append(f"{file_path} ")
                                tool_logs.append("with ",style="dim white")
                                tool_logs.append(f"{len(replace_block_lines)} ")
                                tool_logs.append("addition and ",style="dim white")
                                tool_logs.append(f"{len(search_block_lines)} ")
                                tool_logs.append("removal\n",style="dim white")
                                if search_block:
                                    for line in search_block_lines:
                                        tool_logs.append("       ")
                                        tool_logs.append(f"- {line}\n",style="white on #961b1b")
                                if replace_block:
                                    if not search_block:
                                        # If there's no search block, we still need standard styling
                                        pass
                                    for line in replace_block_lines:
                                        tool_logs.append("       ")
                                        tool_logs.append(f"+ {line}\n",style="white on #26753a")
                            
                            tool_logs.append("\n")
                            if text_response:
                                self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                            else:
                                self.call_from_thread(raven_card.update, tool_logs)
                            self.call_from_thread(raven_card.scroll_visible)
                        elif not tool_meta.get("ignore_display"):
                            display_name = tool_meta["display_name"]
                            arg_key = tool_meta["display_arg"]
                            display_val = tool_args.get(arg_key, "") if arg_key else ""
                            
                            # Add a bold bullet circle before the tool name
                            tool_logs.append(f"\n• {display_name}")
                            tool_logs.append(f"({display_val})\n",style="dim white")
                            if text_response:
                                self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                            else:
                                self.call_from_thread(raven_card.update, tool_logs)
                            self.call_from_thread(raven_card.scroll_visible)
                        try:
                            result = tool_meta["fn"](**tool_args)
                        except Exception as e:
                            result = f"Error: {e}"
                    else:
                        result = "Error: Tool not found."
                    tool_responses.append(types.Part.from_function_response(name=tool_name, response={"result": result}))
                query = tool_responses

            elapsed = time.time() - start_time
            if elapsed >= 60:
                mins = int(elapsed // 60)
                secs = elapsed % 60
                time_str = f"{mins}m {secs:.1f}s"
            else:
                time_str = f"{elapsed:.1f}s"
            
            tool_logs.append(f"\n\nGeneration took {time_str}",style="dim white")
            if text_response:
                self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
            else:
                self.call_from_thread(raven_card.update, tool_logs)
            self.call_from_thread(raven_card.scroll_visible)
                
        except Exception as e:
            self.call_from_thread(raven_card.update, Markdown(f"**Error:** {e}"))


# --- To run it directly for testing ---
if __name__ == "__main__":
    app = RavenTUI()
    app.run()