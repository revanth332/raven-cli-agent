import threading
from textual.app import App, ComposeResult
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.containers import VerticalScroll,Horizontal,Vertical
from textual import work
from textual.widgets import Footer, Static

from rich.markdown import Markdown
from rich.console import Group
from rich.text import Text

from agent.tools.tool_registry import TOOL_REGISTRY
from agent.core.llm import get_chat_session
from agent.utils import read_prompt_from_file,get_active_project_name
from agent.core.settings import settings
from agent.core.safety import is_command_dangerous
from agent.terminal_ui.chat_input import ChatInput
from agent.terminal_ui.permission_box import PermissionBox, PermissionBar
from agent.terminal_ui.thinking_loader import ThinkingMessage
from agent.terminal_ui.model_select_modal import ModelSelectModal
from agent.terminal_ui.session_select_modal import SessionSelectModal
from agent.terminal_ui.sidebar import ConsumptionSidebar
from agent.core.session_manager import create_session, list_sessions

from pathlib import Path
import json
import time

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
    "/exit":{
        "description":"Exit Raven CLI Agent",
        "placeholder":"/exit",
        "system_prompt":""
    },
    "/new":{
        "description":"Start a new chat session",
        "placeholder":"/new",
        "system_prompt":""
    },
    "/sessions":{
        "description":"List and switch chat sessions",
        "placeholder":"/sessions",
        "system_prompt":""
    },
    "/switch":{
        "description":"Switch active chat session",
        "placeholder":"/switch",
        "system_prompt":""
    },
    "/model":{
        "description":"Switch active AI model",
        "placeholder":"/model",
        "system_prompt":""
    },
    "/auto-approve":{
        "description":"Toggle Auto-Approval Mode",
        "placeholder":"/auto-approve",
        "system_prompt":""
    },
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

    #workspace_container {
        height: 1fr;
        width: 100%;
    }

    #main_container {
        height: 1fr;
        width: 1fr;
    }

    #main_container.centered {
        height: 1fr;
        align: center middle;
    }

    #main_container.centered #history {
        height: auto;
        max-height: 50%;
        width: 60%;
        min-width: 50;
        align: center middle;
        content-align: center middle;
        margin-bottom: 1;
    }

    #main_container.centered #bottom_bar {
        dock: none;
        height: auto;
        width: 60%;
        min-width: 50;
        align: center middle;
        padding: 0;
        margin: 1 0;
    }

    #welcome-container {
        align: center middle;
        content-align: center middle;
        width: 100%;
        height: auto;
    }

    .logo-text {
        width: auto;
        height: auto;
        content-align: center middle;
    }

    .version-text {
        width: auto;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding-top: 1;
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
        color: #F8FAFC;
        background: #1e1e1e;
        border: none;
        border-left: heavy #06B6D4;
        padding: 1 2;
    }
    
    .raven-msg {
        color: #ECFDF5;
    }

    ChatInput {
        border: none;
        border-left: heavy #06B6D4;
        margin: 0;
        padding: 1 2;
        color: #F8FAFC;         /* Bright text while typing */
        height: auto;
        min-height: 2;
        max-height: 10;
        background: #1e1e1e;
    }
    
    ChatInput > .text-area--background {
        background: transparent;
    }
    
    ChatInput:focus {
        border: none;
        border-left: heavy #22D3EE;
        background: #1e1e1e;
    }

    #input_status {
        border: none;
        border-left: heavy #06B6D4;
        margin: 0;
        padding: 0 2 1 2;
        height: auto;
        background: #1e1e1e;
    }
    
    #permission_bar {
        background: #1e1e1e;
        border: none;
        border-left: heavy #EF4048;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }
    
    #perm-buttons {
        height: auto;
        margin-top: 1;
    }
    
    #perm-buttons {
        height: auto;
        margin-top: 1;
    }
    
    #perm-buttons Button {
        margin-right: 3;
        min-width: 14;
        height: 1;
        background: transparent;
        border: none;
        text-style: bold;
    }
    #perm-buttons Button:hover {
        background: rgba(255, 255, 255, 0.1);
    }
    #perm-buttons #yes {
        color: #10B981;
        background: transparent;
        border: none;
    }
    #perm-buttons #no {
        color: #FACC15;
        background: transparent;
        border: none;
    }
    #thinking_container {
        height: auto;
        border: none;
        margin-bottom: 1;
        padding: 0 1;
    }
    #bottom_bar {
        dock: bottom;
        height: auto;
        padding: 1 2 1 2;
    }
    #autocomplete_list {
        display: none;
        max-height: 10;
        border: none;
        border-left: heavy #06B6D4;
        margin: 0;
        padding: 1 0;
        background: #1e1e1e;
        scrollbar-size: 1 1;
    }

    #autocomplete_list > .option-list--option {
        padding: 0 2;
    }

    #autocomplete_list > .option-list--option-highlighted {
        background: #2d3748;
        color: #38BDF8;
    }
    """
    # Define system hotkeys for the footer
    BINDINGS = [
        ("escape", "cancel_generation", "Stop Generation"),
        ("q", "quit", "Quit"),
    ]

    active_suggestions = []
    def on_mount(self):
        """Runs the exact moment the UI mounts to the screen."""
        self.chat_session = None

        self.permission_event = threading.Event()
        self.cancel_event = threading.Event()
        self.permission_result = False
        self.permission_instruction = ""
        self.pending_permission = False
        self.is_generating = False

        self.initialize_ai()

    def on_unmount(self) -> None:
        """Ensures background worker threads unblock and exit cleanly on application shutdown."""
        self.pending_permission = False
        self.permission_result = False
        self.cancel_event.set()
        self.permission_event.set()

    def action_quit(self) -> None:
        """Cleanly quits the application."""
        self.on_unmount()
        self.exit()

    def action_cancel_generation(self):
        """Interrupts the active AI generation or denies pending permission."""
        if self.pending_permission:
            self.resolve_permission(granted=False, instruction="")
            return

        self.cancel_event.set()
        # Close option list if it's open, just in case
        autocomplete = self.query_one("#autocomplete_list", OptionList)
        if autocomplete.styles.display == "block":
            autocomplete.styles.display = "none"
            self.query_one("#chat_input", ChatInput).styles.margin = (0, 0, 0, 0)

    def on_text_area_changed(self, event):
        val = event.text_area.text.strip()
        autocomplete = self.query_one("#autocomplete_list",OptionList)
        chat_input = self.query_one("#chat_input", ChatInput)
        if val.startswith("/") and " " not in val:
            matches = [(cmd,info) for cmd,info in SLASH_COMMANDS.items() if cmd.startswith(val)]
            if matches:
                autocomplete.clear_options()
                self.active_suggestions = [m[0] for m in matches]

                for cmd,info in matches:
                    autocomplete.add_option(Option(prompt=f"{cmd:<10} - {info['description']}"))
                autocomplete.styles.display = "block"
                chat_input.styles.margin = (0, 0, 0, 0)
                return
        autocomplete.styles.display = "none"
        chat_input.styles.margin = (0, 0, 0, 0)
    
    def select_autocomplete_option(self):
        autocomplete = self.query_one("#autocomplete_list", OptionList)
        selected_id = autocomplete.highlighted
        if selected_id is None and self.active_suggestions:
            selected_id = 0

        if selected_id is not None and selected_id < len(self.active_suggestions):
            cmd = self.active_suggestions[selected_id]

            chat_input = self.query_one("#chat_input", ChatInput)
            autocomplete.styles.display = "none"
            chat_input.styles.margin = (0, 0, 0, 0)

            if cmd == "/exit":
                chat_input.text = ""
                self.exit()
                return

            if cmd == "/model":
                chat_input.text = ""
                self.open_model_select_modal()
                return

            if cmd in ["/sessions", "/switch"]:
                chat_input.text = ""
                self.open_session_select_modal()
                return

            if cmd == "/new":
                chat_input.text = ""
                self.start_new_session()
                return

            chat_input.text = cmd + " "
            chat_input.action_cursor_line_end()

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
                self.select_autocomplete_option()
                event.prevent_default()
                event.stop()
            

    def ask_permission_ui(self, title: str, message: str):
        """Pushes the permission bar above the chat input area."""
        self.pending_permission = True
        self.permission_result = False
        self.permission_instruction = ""

        def on_allow():
            self.resolve_permission(granted=True, instruction="")

        def on_deny():
            self.resolve_permission(granted=False, instruction="")

        bottom_bar = self.query_one("#bottom_bar")
        chat_input = self.query_one("#chat_input", ChatInput)

        try:
            old_bar = self.query_one("#permission_bar")
            old_bar.remove()
        except Exception:
            pass

        bar = PermissionBar(title, message, on_allow, on_deny)
        bottom_bar.mount(bar, before=chat_input)

        chat_input.placeholder = "Press Enter to allow, or type instruction & Enter to deny/modify..."
        chat_input.focus()

    def resolve_permission(self, granted: bool, instruction: str = ""):
        """Resolves the active permission request and restores standard input state."""
        if not self.pending_permission:
            return

        self.pending_permission = False
        self.permission_result = granted
        self.permission_instruction = instruction

        try:
            bar = self.query_one("#permission_bar")
            bar.remove()
        except Exception:
            pass

        chat_input = self.query_one("#chat_input", ChatInput)
        chat_input.placeholder = "Ask Raven something... (Shift+Enter for newline, 'exit' to quit)"
        chat_input.focus()

        self.permission_event.set()

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
            self.call_from_thread(self.reload_history_ui)
            self.call_from_thread(self.update_status_bar)
            self.call_from_thread(self.notify, "Raven AI Engine initialized!", title="System", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Error initializing AI: {e}", title="Error", severity="error")

    def compose(self) -> ComposeResult:
        """Assembles the physical widgets on the screen."""
        active_model = settings.RAVEN_MODEL
        current_project = get_active_project_name()
        project_or_folder = current_project if current_project else str(Path.cwd())
        approve_status = "[bold #10B981]Auto (Safeguarded)[/bold #10B981]" if settings.RAVEN_AUTO_APPROVE else "[bold #EF4048]Manual[/bold #EF4048]"
        
        with Horizontal(id="workspace_container"):
            with Vertical(id="main_container", classes="centered"):
                with VerticalScroll(id="history") as history:
                    # Add a welcome card on boot
                    yield Vertical(
                        Static(
                            f"[bold #06B6D4]RAVEN CLI AGENT v1.0.0[/bold #06B6D4]\n"
                            f"[dim]Ready to assist. Type below to begin.[/dim]\n\n"
                            f"[bold #06B6D4]Active Model:[/bold #06B6D4] {active_model}  │  "
                            f"[bold #06B6D4]{'Project' if current_project else 'Folder'}:[/bold #06B6D4] {project_or_folder}\n"
                            f"[bold #06B6D4]Agent Version:[/bold #06B6D4] 1.0.0 (Raven Personal AI Developer Agent)",
                            classes="version-text"
                        ),
                        id="welcome-container"
                    )
                with Vertical(id="bottom_bar"):
                    yield Horizontal(id="thinking_container")
                    yield OptionList(id="autocomplete_list")
                    yield ChatInput(id="chat_input", show_line_numbers=False, placeholder="Ask Raven something... (Shift+Enter for newline, 'exit' to quit)")
                    yield Static(
                        f"[dim #64748B]Model:[/dim #64748B] [bold #06B6D4]{active_model}[/bold #06B6D4]  │  [dim #64748B]Approve:[/dim #64748B] {approve_status}",
                        id="input_status"
                    )
            yield ConsumptionSidebar(id="sidebar")
        yield Footer()

    # --- EVENT HANDLERS ---
    def update_status_bar(self) -> None:
        try:
            active_model = settings.RAVEN_MODEL
            approve_status = "[bold #10B981]Auto (Safeguarded)[/bold #10B981]" if settings.RAVEN_AUTO_APPROVE else "[bold #EF4048]Manual[/bold #EF4048]"
            session_title = getattr(self.chat_session, "session_title", "New Conversation") if self.chat_session else "New Conversation"
            current_project = get_active_project_name()
            project_name = current_project if current_project else Path.cwd().name

            status_widget = self.query_one("#input_status", Static)
            status_widget.update(
                f"[dim #64748B]Model:[/dim #64748B] [bold #06B6D4]{active_model}[/bold #06B6D4]  │  [dim #64748B]Approve:[/dim #64748B] {approve_status}"
            )

            try:
                sidebar = self.query_one(ConsumptionSidebar)
                metrics = self.chat_session.get_context_usage() if self.chat_session else None
                sidebar.update_metrics(metrics=metrics, session_name=session_title, project_name=project_name)
            except Exception:
                pass
        except Exception:
            pass

    def start_new_session(self) -> None:
        new_sess = create_session(model_name=settings.RAVEN_MODEL)
        self.chat_session = get_chat_session(session_id=new_sess["session_id"])
        self.reload_history_ui()
        self.update_status_bar()
        self.notify("Started a fresh chat session!", title="Session Created", severity="information")

    def open_session_select_modal(self) -> None:
        def on_session_dismiss(selected_session_id: str | None) -> None:
            if selected_session_id:
                self.chat_session = get_chat_session(session_id=selected_session_id)
                self.reload_history_ui()
                self.update_status_bar()
                try:
                    sidebar = self.query_one(ConsumptionSidebar)
                    sidebar.update_metrics(self.chat_session.get_context_usage())
                except Exception:
                    pass
                self.notify(f"Switched session to '{self.chat_session.session_title}'", title="Session Changed", severity="information")
            else:
                if self.chat_session:
                    active_id = getattr(self.chat_session, "session_id", None)
                    if active_id:
                        sessions = list_sessions()
                        if not any(s["session_id"] == active_id for s in sessions):
                            if sessions:
                                self.chat_session = get_chat_session(session_id=sessions[0]["session_id"])
                                self.notify(f"Active session was deleted. Switched to '{self.chat_session.session_title}'", title="Session Changed", severity="warning")
                            else:
                                self.start_new_session()
                            self.reload_history_ui()
                            self.update_status_bar()

        self.push_screen(SessionSelectModal(), on_session_dismiss)

    def reload_history_ui(self) -> None:
        try:
            history_container = self.query_one("#history")
            # Remove all children except welcome container if desired, or clear all
            history_container.remove_children()

            if not self.chat_session or len(self.chat_session.messages) <= 1:
                # Mount default welcome container
                active_model = settings.RAVEN_MODEL
                current_project = get_active_project_name()
                project_or_folder = current_project if current_project else str(Path.cwd())
                welcome_widget = Vertical(
                    Static(
                        f"[bold #06B6D4]RAVEN CLI AGENT v1.0.0[/bold #06B6D4]\n"
                        f"[dim]Ready to assist. Type below to begin.[/dim]\n\n"
                        f"[bold #06B6D4]Session:[/bold #06B6D4] {getattr(self.chat_session, 'session_title', 'New Conversation')}  │  "
                        f"[bold #06B6D4]Active Model:[/bold #06B6D4] {active_model}\n"
                        f"[bold #06B6D4]{'Project' if current_project else 'Folder'}:[/bold #06B6D4] {project_or_folder}",
                        classes="version-text"
                    ),
                    id="welcome-container"
                )
                history_container.mount(welcome_widget)
            else:
                main_container = self.query_one("#main_container")
                if main_container.has_class("centered"):
                    main_container.remove_class("centered")

                for msg in self.chat_session.messages:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role == "user" and content:
                        card = Static(classes="message user-msg")
                        card.update(Markdown(content))
                        history_container.mount(card)
                    elif role == "assistant" and content:
                        card = Static(classes="message raven-msg")
                        card.update(Markdown(content))
                        history_container.mount(card)

            self.scroll_to_bottom()
        except Exception:
            pass

    def open_model_select_modal(self) -> None:
        def on_model_dismiss(selected_model: str | None) -> None:
            if selected_model and selected_model != settings.RAVEN_MODEL:
                settings.set_config({"RAVEN_MODEL": selected_model})
                self.initialize_ai()
                self.update_status_bar()
                self.notify(f"Switched model to {selected_model}", title="Model Changed", severity="information")

        self.push_screen(ModelSelectModal(current_model=settings.RAVEN_MODEL), on_model_dismiss)

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Triggers when the user presses 'Enter' in the input box."""
        if self.pending_permission:
            user_text = event.value.strip()
            input_widget = event.text_area
            input_widget.text = ""
            if not user_text:
                self.resolve_permission(granted=True, instruction="")
            else:
                self.resolve_permission(granted=False, instruction=user_text)
            return

        if self.is_generating:
            self.notify("A response is currently generating. Please wait or press Esc to cancel.", title="Busy", severity="warning")
            return

        user_input = event.value.strip()
        
        if not user_input:
            return
            
        if user_input.lower() in ["exit", "quit", "/exit"] or user_input.lower().startswith("/exit"):
            self.exit()
            return
        
        if user_input.lower() in ["/sessions", "/switch"] or user_input.lower().startswith("/sessions ") or user_input.lower().startswith("/switch "):
            input_widget = event.text_area
            input_widget.text = ""
            self.query_one('#autocomplete_list', OptionList).styles.display = "none"
            self.open_session_select_modal()
            return

        if user_input.lower() == "/new" or user_input.lower().startswith("/new "):
            input_widget = event.text_area
            input_widget.text = ""
            self.query_one('#autocomplete_list', OptionList).styles.display = "none"
            self.start_new_session()
            return

        if user_input.lower() == "/model" or user_input.lower().startswith("/model "):
            input_widget = event.text_area
            input_widget.text = ""
            self.query_one('#autocomplete_list', OptionList).styles.display = "none"
            self.open_model_select_modal()
            return
        
        if user_input.lower() == "/auto-approve" or user_input.lower().startswith("/auto-approve "):
            new_val = not settings.RAVEN_AUTO_APPROVE
            settings.set_config({"RAVEN_AUTO_APPROVE": new_val})
            self.update_status_bar()
            
            input_widget = event.text_area
            input_widget.text = ""
            self.query_one('#autocomplete_list', OptionList).styles.display = "none"
            
            history_container = self.query_one("#history")
            main_container = self.query_one("#main_container")
            if main_container.has_class("centered"):
                main_container.remove_class("centered")
                
            status_str = "[green]Enabled[/green] (Safeguarded)" if new_val else "[red]Disabled[/red] (Manual)"
            info_card = Static(classes="message raven-msg")
            info_card.update(Markdown(f"**System:** Auto-Approval is now **{status_str}**."))
            history_container.mount(info_card)
            self.scroll_to_bottom()
            return
        
        main_container = self.query_one("#main_container")
        if main_container.has_class("centered"):
            main_container.remove_class("centered")

        self.query_one('#autocomplete_list',OptionList).styles.display = "none"
        self.query_one('#chat_input', ChatInput).styles.margin = (0, 0, 0, 0)
        # Clear the input box immediately for the next question
        input_widget = event.text_area
        input_widget.text = ""

        # 1. Echo the user's message into the scrollable history area
        history_container = self.query_one("#history")
        
        user_card = Static(classes="message user-msg")
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
                user_message_committed = query is None
                for attempt in range(max_retries):
                    try:
                        self.call_from_thread(thinking_container.mount,thinking_message)
                        generator = self.chat_session.send_message_stream(query)
                        if query is not None and not user_message_committed:
                            self.chat_session.commit_user_message(query)
                            user_message_committed = True
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

                if text_response or function_calls:
                    assistant_tool_calls = None
                    if function_calls:
                        assistant_tool_calls = []
                        for _,fc in function_calls.items():
                            assistant_tool_calls.append({
                                "id":fc["id"],
                                "type":"function",
                                "function":{
                                    "name":fc["name"],
                                    "arguments":fc["arguments"]
                                },
                                "extra_content":fc.get("extra_content","")
                            })
                    self.chat_session.commit_assistant_message(content=text_response or None,tool_calls=assistant_tool_calls)

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
                        
                        if tool_name in ["execute_command", "commit_staged_git_changes"]:
                            bypass_prompt = False
                            if settings.RAVEN_AUTO_APPROVE:
                                if tool_name == "commit_staged_git_changes":
                                    bypass_prompt = True
                                elif tool_name == "execute_command":
                                    cmd_str = tool_args.get("command", "")
                                    if not is_command_dangerous(cmd_str):
                                        bypass_prompt = True

                            if not bypass_prompt:
                                self.permission_event.clear()
                                title = f"Action Required: {tool_name}"
                                msg = f"Raven wants to execute {tool_name}.\nArgs: {str(tool_args)}"
                                self.call_from_thread(self.ask_permission_ui, title, msg)
                                self.permission_event.wait()

                                if self.cancel_event.is_set():
                                    break

                                if not self.permission_result:
                                    instr = getattr(self, "permission_instruction", "")
                                    if instr:
                                        result = f"User denied permission and provided instructions: '{instr}'"
                                        tool_logs.append(f"\nPermission Denied (Instruction: \"{instr}\")\n", style="bold red")
                                    else:
                                        result = "Error: User denied permission."
                                        tool_logs.append("\nPermission Denied\n", style="bold red")

                                    tool_responses_to_append.append({
                                        "role": "tool",
                                        "tool_call_id": fc["id"],
                                        "name": fc["name"],
                                        "content": result
                                    })
                                    if text_response:
                                        self.call_from_thread(raven_card.update, Group(tool_logs, Markdown(text_response)))
                                    else:
                                        self.call_from_thread(raven_card.update, tool_logs)
                                    self.call_from_thread(self.scroll_to_bottom)
                                    continue

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
                                if display_val:
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

            if self.chat_session:
                summary = self.chat_session.record_turn_usage(assistant_response=text_response)
                try:
                    sidebar = self.query_one(ConsumptionSidebar)
                    session_title = getattr(self.chat_session, "session_title", "New Conversation")
                    current_project = get_active_project_name()
                    project_name = current_project if current_project else Path.cwd().name
                    self.call_from_thread(sidebar.update_metrics, summary, session_title, project_name)
                except Exception:
                    pass
                
        except Exception as e:
            self.call_from_thread(raven_card.update, Markdown(f"**Error:** {e}"))
        finally:
            self.is_generating = False


# --- To run it directly for testing ---
if __name__ == "__main__":
    app = RavenTUI()
    app.run()
