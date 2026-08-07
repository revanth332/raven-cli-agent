
from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, Button, TextArea
from textual.binding import Binding
from textual.message import Message
from textual.containers import VerticalScroll,Horizontal,Vertical
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from rich.markdown import Markdown
from textual import work
import threading
from agent.main import TOOL_REGISTRY
import time
from rich.console import Group
from rich.text import Text

from agent.llm import get_chat_session
from agent.utils import read_prompt_from_file,get_active_project_name
from agent.settings import settings

import json

raven_logo = """
 ██████╗  █████╗ ██╗   ██╗███████╗███╗   ██╗
 ██╔══██╗██╔══██╗██║   ██║██╔════╝████╗  ██║
 ██████╔╝███████║██║   ██║█████╗  ██╔██╗ ██║
 ██╔══██╗██╔══██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║
 ██║  ██║██║  ██║ ╚████╔╝ ███████╗██║ ╚████║
 ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝
    """

DEBUG_PROMPT = read_prompt_from_file("prompts/debug_prompt.md")
COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.md")
REPORT_PROMPT = read_prompt_from_file("prompts/report_prompt.md")
REVIEW_PROMPT = read_prompt_from_file("prompts/review_prompt.md")
PLAN_PROMPT = read_prompt_from_file("prompts/plan_prompt.md")
ASK_PROMPT = read_prompt_from_file("prompts/ask_prompt.md")
EXPLAIN_PROMPT=read_prompt_from_file("prompts/explain_prompt.md")

SLASH_COMMANDS = {
    "/coach":{
        "description":"Activate coach mode",
        "placeholder":"/coach",
        "system_prompt":COACH_PROMPT
    },
    "/debug":{
        "description":"Activate debug mode",
        "placeholder":"/debug",
        "system_prompt":DEBUG_PROMPT
    },
    "/report":{
        "description":"Generate past work report",
        "placeholder":"/report <week/month/..>",
        "system_prompt":REPORT_PROMPT
    },
    "/plan":{
        "description":"Generate a comprehensive plan",
        "placeholder":"/plan",
        "system_prompt":PLAN_PROMPT
    },
    "/review":{
        "description":"Generates a comprehensive code review",
        "placeholder":"/review <week/month/..>",
        "system_prompt":REVIEW_PROMPT
    },
    "/ask":{
        "description":"Generates a architectural guidance",
        "placeholder":"/ask <week/month/..>",
        "system_prompt":ASK_PROMPT
    },
    "/explain":{
        "description":"Generates a comprehensive explanation",
        "placeholder":"/explain <week/month/..>",
        "system_prompt":EXPLAIN_PROMPT
    }
}

class ChatInput(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("shift+enter", "newline", "Newline", priority=True),
    ]

    class Submitted(Message):
        def __init__(self, text_area: "ChatInput", value: str) -> None:
            self.text_area = text_area
            self.value = value
            super().__init__()

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self, self.text))

    def action_newline(self) -> None:
        self.insert("\n")

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

    ChatInput {
        border: solid #06B6D4; /* Brilliant double sky-blue border */
        margin: 1 1;
        padding: 0 1;
        color: #F8FAFC;         /* Bright text while typing */
        height: auto;
        min-height: 3;
        max-height: 10;
        background: transparent;
    }
    
    ChatInput > .text-area--background {
        background: transparent;
    }
    
    ChatInput:focus {
        border: solid #06B6D4;
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
    #autocomplete_list {
        display: none;
        layer: overlay;
        dock: bottom;
        offset-y: -6;
        height: 6;
        width: 1fr;
        max-height:8;
        background:#1e1e1e;
        border:tall #00d7af;
    }
    """
    # Define system hotkeys for the footer
    BINDINGS = [
        ("escape", "cancel_generation", "Stop Generation"),
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Exit"),
    ]

    active_suggestions = []
    def on_mount(self):
        """Runs the exact moment the UI mounts to the screen."""
        self.chat_session = None

        self.permission_event = threading.Event()
        self.cancel_event = threading.Event()
        self.permission_result = False
        self.is_generating = False

        self.initialize_ai()

    def action_cancel_generation(self):
        """Interrupts the active AI generation."""
        self.cancel_event.set()
        # Close option list if it's open, just in case
        autocomplete = self.query_one("#autocomplete_list", OptionList)
        if autocomplete.styles.display == "block":
            autocomplete.styles.display = "none"

    def on_text_area_changed(self, event):
        val = event.text_area.text.strip()
        autocomplete = self.query_one("#autocomplete_list",OptionList)
        if val.startswith("/") and " " not in val:
            matches = [(cmd,info) for cmd,info in SLASH_COMMANDS.items() if cmd.startswith(val)]
            if matches:
                autocomplete.clear_options()
                self.active_suggestions = [m[0] for m in matches]

                for cmd,info in matches:
                    autocomplete.add_option(Option(prompt=f"{cmd:<10} - {info['description']}"))
                autocomplete.styles.display = "block"
                return
        autocomplete.styles.display = "none"
    
    def on_key(self,event):
        autocomplete = self.query_one("#autocomplete_list",OptionList)

        if autocomplete.styles.display == "block":
            if event.key == "down":
                autocomplete.action_cursor_down()
                event.prevent_default()
            elif event.key == "up":
                autocomplete.action_cursor_up()
                event.prevent_default()
            elif event.key in ["tab","enter"]:
                selected_id = autocomplete.highlighted
                if selected_id is not None and selected_id < len(self.active_suggestions):
                    cmd = self.active_suggestions[selected_id]

                    chat_input = self.query_one("#chat_input", ChatInput)
                    chat_input.text = cmd + " "
                    chat_input.action_cursor_line_end()

                    autocomplete.styles.display = "none"
                    event.prevent_default()
            

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

    def scroll_to_bottom(self):
        """Scrolls the chat history container to the very bottom."""
        try:
            self.query_one("#history").scroll_end(animate=False)
        except Exception:
            pass
    
    @work(thread=True)
    def initialize_ai(self):
        """Background task to load credentials and initialize Gemini."""
        try:
            self.chat_session = get_chat_session()
            self.is_generating = False
            self.call_from_thread(self.notify, "Raven AI Engine initialized!", title="System", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Error initializing AI: {e}", title="Error", severity="error")

    def compose(self) -> ComposeResult:
        """Assembles the physical widgets on the screen."""
        # VerticalScroll acts as our scrollable conversation container
        active_model = settings.RAVEN_MODEL
        current_project = get_active_project_name()
        
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
        yield OptionList(id="autocomplete_list")
        # Create a single docked container at the bottom
        with Vertical(id="bottom_bar"):
            yield Horizontal(id="thinking_container")
            yield ChatInput(id="chat_input", show_line_numbers=False, placeholder="Ask Raven something... (Shift+Enter for newline, 'exit' to quit)")
            yield Footer()

    # --- EVENT HANDLERS ---
    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Triggers when the user presses 'Enter' in the input box."""
        if self.is_generating:
            self.notify("A response is currently generating. Please wait or press Esc to cancel.", title="Busy", severity="warning")
            return

        user_input = event.value.strip()
        
        if not user_input:
            return
            
        if user_input.lower() in ["exit", "quit"]:
            self.exit()
            return
        
        self.query_one('#autocomplete_list',OptionList).styles.display = "none"
        # Clear the input box immediately for the next question
        input_widget = event.text_area
        input_widget.text = ""

        # 1. Echo the user's message into the scrollable history area
        history_container = self.query_one("#history")
        
        user_card = Static(classes="message user-msg")
        user_card.border_title = "User"
        user_card.styles.border = ("round", "#06B6D4")
        user_card.update(Markdown(user_input))
        history_container.mount(user_card)

        if user_input.startswith("/"):
            parts = user_input.split(" ",1)
            cmd = parts[0].lower()
            query = parts[1].lower().strip() if len(parts) > 1 else ""

            if cmd == "/report":
                user_input = SLASH_COMMANDS[cmd]['system_prompt'].replace("{timeperiod}",query)
            else:
                user_input = f"{SLASH_COMMANDS[cmd]['system_prompt']}\n {query}"

        # 2. Echo a mock response from Raven for now
        raven_card = Static()
        history_container.mount(raven_card)
        self.scroll_to_bottom()

        self.is_generating = True
        self.stream_response(user_input,raven_card)
        
    
    @work(thread=True)
    def stream_response(self,query:str,raven_card:Static):
        """Background thread that streams the AI response without freezing the UI."""
        if not self.chat_session:
            self.call_from_thread(raven_card.update, "[red]AI is still initializing. Please try again.[/red]")
            return
        start_time = time.time()
        self.cancel_event.clear()
        try:
            thinking_container = self.query_one("#thinking_container")
            text_response = ""
            tool_logs = Text()
            while True:
                if self.cancel_event.is_set():
                    break
                    
                function_calls = {}
                max_retries = 5
                thinking_message = ThinkingMessage("")
                for attempt in range(max_retries):
                    try:
                        self.call_from_thread(thinking_container.mount,thinking_message)
                        generator = self.chat_session.send_message_stream(query)
                        for chunk in generator:
                            if self.cancel_event.is_set():
                                break
                            if not chunk.choices:
                                continue
                            delta = chunk.choices[0].delta
                            if hasattr(delta,"tool_calls") and delta.tool_calls:
                                for tool_call in delta.tool_calls:
                                    tool_idx = tool_call.index
                                    if tool_idx not in function_calls:
                                        function_calls[tool_idx] = {"id":"","name":"","arguments":""}
                                    if tool_call.id:
                                        function_calls[tool_idx]["id"] = tool_call.id
                                    if tool_call.function.name:
                                        function_calls[tool_idx]["name"] += tool_call.function.name
                                    if tool_call.function.arguments:
                                        function_calls[tool_idx]["arguments"] += tool_call.function.arguments
                                    if getattr(tool_call, 'extra_content', None):
                                        if isinstance(tool_call.extra_content,str): function_calls[tool_idx]["extra_content"] += tool_call.extra_content
                                        else: function_calls[tool_idx]["extra_content"] = tool_call.extra_content
                            
                            if hasattr(delta,"content") and delta.content:
                                text_response += delta.content
                                if tool_logs:
                                    self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                                else:
                                    self.call_from_thread(raven_card.update, Markdown(text_response))
                                self.call_from_thread(self.scroll_to_bottom)
                        break
                    except Exception as api_error:
                        if thinking_message:                                                                                                                                
                            self.call_from_thread(thinking_message.remove)
                        error_str = str(api_error).lower()
                        if "429" in error_str or "exhausted" in error_str or "quota" in error_str:
                            if attempt < max_retries - 1:
                                # Exponential backoff: 2, 4, 8, 16 seconds...
                                sleep_time = 2 ** (attempt + 1) 
                                msg = f"*API Rate Limit hit. (Retrying in {sleep_time}s)*"
                                self.call_from_thread(raven_card.update, Markdown(msg))
                                time.sleep(sleep_time)
                                continue
                        raise api_error
                if thinking_message:
                    self.call_from_thread(thinking_message.remove)

                if self.cancel_event.is_set():
                    tool_logs.append("\n\nGeneration stopped by user.")
                    break

                if not function_calls:
                    break

                tool_calls_to_append = []
                tool_responses_to_append = []
                for _,fc in function_calls.items():
                    if self.cancel_event.is_set():
                        break
                        
                    tool_name = fc["name"]
                    try:
                        tool_args = json.loads(fc["arguments"])
                    except Exception as e:
                        raise e
                    tool_calls_to_append.append({
                        "id":fc["id"],
                        "type":"function",
                        "function":{
                            "name":fc["name"],
                            "arguments":fc["arguments"]
                        },
                        "extra_content":fc.get("extra_content","")
                    })

                    if tool_name in TOOL_REGISTRY:
                        tool_meta = TOOL_REGISTRY[tool_name]
                        
                        if tool_name in ["execute_command", "run_ui_test","commit_staged_git_changes"]:
                            self.permission_event.clear()
                            title = f"Action Required: {tool_name}"
                            msg = f"Raven wants to execute {tool_name}.\nArgs: {str(tool_args)}"
                            self.call_from_thread(self.ask_permission_ui,title,msg)
                            self.permission_event.wait()

                            if not self.permission_result:
                                result = "Error: User denied permission."
                                tool_responses_to_append.append({
                                                            "role": "tool",
                                                            "tool_call_id": fc["id"],
                                                            "name": fc["name"],
                                                            "content": result
                                                        })
                                continue
                            tool_logs.append(f"\n• {tool_meta['display_name']}")
                            tool_logs.append(f"({str(tool_args)})\n",style="dim white")
                            if text_response:
                                self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                            else:
                                self.call_from_thread(raven_card.update, tool_logs)
                            self.call_from_thread(self.scroll_to_bottom)

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
                            self.call_from_thread(self.scroll_to_bottom)
                        elif not tool_meta.get("ignore_display"):
                            display_name = tool_meta["display_name"]
                            tool_logs.append(f"\n• {display_name}")

                            arg_keys = tool_meta["display_arg"]
                            if arg_keys:
                                if(isinstance(arg_keys,str)):
                                    display_val = tool_args.get(arg_keys, "") if arg_keys else ""
                                if(isinstance(arg_keys,list)):
                                    display_val = ",".join([tool_args.get(key, "") for key in arg_keys])
                                tool_logs.append(f"({display_val})\n",style="dim white")
                            else:
                                tool_logs.append("\n")
                            if text_response:
                                self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                            else:
                                self.call_from_thread(raven_card.update, tool_logs)
                            self.call_from_thread(self.scroll_to_bottom)
                        try:
                            result = tool_meta["fn"](**tool_args)
                        except Exception as e:
                            result = f"Error: {e}"
                    else:
                        result = "Error: Tool not found."
                    tool_responses_to_append.append({
                                                "role": "tool",
                                                "tool_call_id": fc["id"],
                                                "name": fc["name"],
                                                "content": json.dumps(result)
                                            })
                self.chat_session.add_message("assistant",tool_calls=tool_calls_to_append)
                for tool_response in tool_responses_to_append:
                    self.chat_session.add_message(role="tool",tool_call_id=tool_response["tool_call_id"],name=tool_response["name"],content=tool_response["content"])
                query = None

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
            self.call_from_thread(self.scroll_to_bottom)
                
        except Exception as e:
            self.call_from_thread(raven_card.update, Markdown(f"**Error:** {e}"))
        finally:
            self.is_generating = False


# --- To run it directly for testing ---
if __name__ == "__main__":
    app = RavenTUI()
    app.run()