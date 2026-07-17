import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.live import Live
from rich.spinner import Spinner
from rich.markdown import Markdown
import questionary
from questionary import Style
from agent.llm import get_chat_session,get_response
from agent.utils import read_prompt_from_file,save_to_memory,find_file,read_file,create_file,execute_command,save_concept,log_successful_debug,save_to_project_memory,get_current_timestamp,patch_file,start_new_backup_turn,update_architecture_map,run_ui_test,update_llm_model,get_staged_git_changes,commit_staged_git_changes,get_active_llm_model
from agent.indexer import search_codebase
from google.genai import types

import sys
from pathlib import Path
import json
import shutil
import subprocess
import time

app = typer.Typer()
console = Console()

chat_style = Style([
            ('question', 'fg:#06B6D4 bold'),
            ('answer', 'fg:#06B6D4'),
        ])

TOOL_REGISTRY = {
    "save_to_memory": {
        "fn": save_to_memory, 
        "display_name": "Remember", 
        "display_arg": "fact", 
        "ignore_display": False
    },
    "find_file": {
        "fn": find_file, 
        "display_name": "Find", 
        "display_arg": "file_path",
        "ignore_display": False
    },
    "read_file": {
        "fn": read_file, 
        "display_name": "Read", 
        "display_arg": "file_path", 
        "ignore_display": False
    },
    "create_file": {
        "fn": create_file, 
        "display_name": "Create", 
        "display_arg": "file_path", 
        "ignore_display": False
    },
    "execute_command": {
        "fn": execute_command, 
        "display_name": "Execute", 
        "display_arg": "command", 
        "ignore_display": True
    },
    "get_current_timestamp": {
        "fn": get_current_timestamp, 
        "display_name": "Time", 
        "display_arg": None, 
        "ignore_display": True # Awesome use case for this! Hides background checks.
    },
    "save_concept": {
        "fn": save_concept, 
        "display_name": "Document Concept", 
        "display_arg": "concept_name", 
        "ignore_display": False
    },
    "log_successful_debug": {
        "fn": log_successful_debug, 
        "display_name": "Log Fix", 
        "display_arg": "error_description", 
        "ignore_display": False
    },
    "save_to_project_memory": {
        "fn": save_to_project_memory, 
        "display_name": "Project Memory", 
        "display_arg": "fact", 
        "ignore_display": False
    },
    "patch_file": {
        "fn": patch_file, 
        "display_name": "Patch", 
        "display_arg": "file_path", 
        "ignore_display": True
    },
    "update_architecture_map": {
        "fn": update_architecture_map, 
        "display_name": "Update Architecture Map", 
        "display_arg": None,
        "ignore_display": False
    },
    "run_ui_test": {
        "fn": run_ui_test, 
        "display_name": "Browser", 
        "display_arg": None,
        "ignore_display": True
    },
    "search_codebase":{
        "fn": search_codebase,
        "display_name": "Searching Codebase",
        "display_arg": "",
        "ignore_display": False
    },
    "get_staged_git_changes":{
        "fn": get_staged_git_changes,
        "display_name": "Search changes",
        "display_arg": "",
        "ignore_display": False
    },
    "commit_staged_git_changes":{
        "fn": commit_staged_git_changes,
        "display_name": "Commit chanegs",
        "display_arg": "message",
        "ignore_display": True
    },
}

def display_welcome():
    # ASCII text logo spelling out 'RAVEN'
    raven_logo = """
 ██████╗  █████╗ ██╗   ██╗███████╗███╗   ██╗
 ██╔══██╗██╔══██╗██║   ██║██╔════╝████╗  ██║
 ██████╔╝███████║██║   ██║█████╗  ██╔██╗ ██║
 ██╔══██╗██╔══██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║
 ██║  ██║██║  ██║ ╚████╔╝ ███████╗██║ ╚████║
 ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝
    """
    
    # 1. Print a little spacing and the logo in sky blue color
    console.print(f"[#06B6D4]{raven_logo}[/#06B6D4]")
    
    # Get welcome info
    active_model = get_active_llm_model()
    current_project = Path.cwd().name
    
    # 2. Add a simple panel welcome message
    welcome_message = (
        "[bold white]Welcome to Raven CLI! How can I help you today?[/bold white]\n\n"
        f"[bold #06B6D4]Active Model:[/bold #06B6D4] {active_model}\n"
        f"[bold #06B6D4]Current Project:[/bold #06B6D4] {current_project}\n"
        f"[bold #06B6D4]Agent Version:[/bold #06B6D4] 1.0.0 (Raven Personal AI Developer Agent)"
    )
    
    welcome_panel = Panel(
        Align.center(welcome_message),
        border_style="#06B6D4",
        expand=False
    )
    console.print(welcome_panel)
    console.print()

def render_stream(generator):
    full_response = ""
    with Live(Markdown(full_response),refresh_per_second=10,console=console) as live:
        for chunk in generator:
            if chunk.function_calls:
                continue
            if hasattr(chunk,'text') and chunk.text:
                full_response += chunk.text
            elif isinstance(chunk,str):
                full_response += chunk
            live.update(Markdown(full_response))
        if not full_response:
            live.update(Text(""))

def run_agent_loop(chat_session,intial_input):
    """The core multi-turn engine of Raven"""
    current_input = intial_input
    max_retries = 5
    while True:
        final_response = ""
        function_calls = []
        with Live(Spinner("dots", text="Thinking...", style="cyan"),refresh_per_second=10,console=console,transient=True) as live:
            for attempt in range(max_retries):
                try:
                    generator = chat_session.send_message_stream(current_input)
                    for chunk in generator:
                        if chunk.function_calls:
                            function_calls.extend(chunk.function_calls)
                            continue
                        if hasattr(chunk,'text') and chunk.text:
                            final_response += chunk.text
                            live.update(Markdown(final_response))
                    break
                except Exception as api_error:
                    error_str = str(api_error)
                    if "429" in error_str or "exhausted" in error_str or "quota" in error_str:
                        if attempt < max_retries - 1:
                            sleep_time = 2**(attempt+1)
                            msg = f"⏳ *API Rate Limit hit. (Retrying in {sleep_time}s)*"
                            console.print(Markdown(msg))
                            time.sleep(sleep_time)
                            continue
                        raise api_error
                
                # Clear or hide the live thinking display if no text was streamed (i.e., only function calls were found)
                if not final_response:
                    live.update(Text(""))
        if len(function_calls) == 0:
            break
        tool_responses = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = fc.args

            if tool_name == "patch_file":
                file_path = tool_args.get('file_path', 'Unknown')
                console.print(f"[bold cyan]• Update[/bold cyan]([dim]{file_path}[/dim])")
                
                search_lines = tool_args.get('search_block', '').rstrip().split('\n')
                replace_lines = tool_args.get('replace_block', '').rstrip().split('\n')
                
                # Print Red Background for removed lines
                for line in search_lines:
                    # We use Text() to prevent Rich from crashing on code brackets []
                    t = Text(f"- {line}")
                    t.stylize("bold white on red")
                    console.print(t)
                    
                # Print Green Background for added lines
                for line in replace_lines:
                    t = Text(f"+ {line}")
                    t.stylize("bold white on dark_green")
                    console.print(t)
                
                console.print()

            if tool_name == "execute_command":
                console.print(f"[bold red]• Execute[/bold red]([dim]{tool_args['command']}[/dim])")
                
                confirmed = typer.confirm("Allow Raven to execute this command?")
                if not confirmed:
                    result = "Error: User denied permission to execute this terminal command."
                    tool_responses.append(
                        types.Part.from_function_response(name=tool_name, response={"result": result})
                    )
                    continue
            
            if tool_name == "run_ui_test":
                console.print(f"[bold red]• Browser[/bold red]()")

                confirmed = typer.confirm("Raven wants to run a UI Automation Script. Allow?")
                if not confirmed:
                    result = "Error: User denied permission to execute this automation script."
                    tool_responses.append(
                        types.Part.from_function_response(name=tool_name, response={"result": result})
                    )
                    continue

            if tool_name == "commit_staged_git_changes":
                console.print(f"[bold cyan]• Commit[/bold cyan]([dim]{tool_args['message']}[/dim]{',[red]unverified[/red]' if not tool_args['is_verified'] else ''})")
                confirmed = typer.confirm("Raven wants to commit the changes. Allow?")
                if not confirmed:
                    result = "Error: User denied permission to commit the changes."
                    tool_responses.append(
                        types.Part.from_function_response(name=tool_name, response={"result": result})
                    )
                    continue
            if tool_name in TOOL_REGISTRY:
                tool_meta = TOOL_REGISTRY[tool_name]
                
                if not tool_meta.get("ignore_display"):
                    display_name = tool_meta["display_name"]
                    arg_key = tool_meta["display_arg"]
                    
                    display_val = tool_args.get(arg_key, "") if arg_key else ""
                    console.print(f"[bold cyan]• {display_name}[/bold cyan]([dim]{display_val}[/dim])")
                try:
                    result = TOOL_REGISTRY[tool_name]["fn"](**tool_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {e}"
            else:
                result = f"Error: Tool {tool_name} not found in registry."
        
            tool_responses.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"result":result}
                )
            )

        current_input = tool_responses

def start_chat_session(chat_session):
    while (True):
        query = questionary.text(
            ">", 
            qmark="",
            style=chat_style
        ).ask()
        if query is None or query.strip().lower() == "exit":
            break
            
        if not query.strip():
            continue
        if query == '/undo':
            registry_file = Path.home() / ".raven" / "backups" / "undo_registry.json"
            if registry_file.exists():
                try:
                    registry = json.loads(registry_file.read_text(encoding='utf-8'))
                    if not registry:
                        console.print("[yellow]No edits were made in the last turn to undo.[/yellow]\n")
                        continue
                    for entry in registry:
                        shutil.copy2(Path(entry["backup"]),Path(entry["original"]))
                    
                    registry_file.write_text("[]",encoding='utf-8')
                    console.print()
                except Exception as e:
                    console.print(f"[red]Failed to undo: {e}[/red]\n")
            else:
                console.print("[yellow]No recent edits to undo.[/yellow]\n")
            continue
        start_new_backup_turn()
        console.print()
        run_agent_loop(chat_session,query)
        console.print()

@app.command()
def test():
    print("testng..")

@app.command()
def chat(coach:bool = typer.Option(False,"--coach",help="Enable Socratic mentor mode.")):
    """
    Start an interactive multi-turn chat session with Raven.
    
    You can chat with Raven to write, edit, find files, or execute commands.
    Type '/undo' inside the chat to revert any file edits from the previous turn.
    Type 'exit' to end the session.
    """
    try:
        with console.status("preparing session..."):
            chat_session = get_chat_session(is_coach=coach)
        display_welcome()
        if coach:
            console.print("[bold magenta]Coach Mode Activated! Raven will guide you, not code for you.[/bold magenta]\n")
        start_chat_session(chat_session)
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

@app.command()
def debug(coach:bool = typer.Option(False,"--coach",help="Enable Socratic mentor mode.")):
    """
    Diagnose and troubleshoot errors by piping log outputs.

      - Linux/Mac/Git Bash: <your-command-or-script> |& reva debug
      - Windows PowerShell: <your-command-or-script> 2>&1 | reva debug
      - Piping file content: cat error.log | reva debug
      
    Raven will analyze the errors and guide you through an interactive troubleshooting session.
    """
    DEBUG_PROMPT = read_prompt_from_file("prompts/debug_prompt.txt")
    if coach:
        console.print("[bold magenta]Coach Mode Activated! Raven will guide you, not code for you.[/bold magenta]\n")
    if sys.stdin.isatty():
        console.print("[red]No input detected. Usage: type error.log | reva debug[/red]")
        raise typer.Exit(1)
    else:
        piped_logs = sys.stdin.read()
        debug_prompt = f"{DEBUG_PROMPT}\n\n{piped_logs}"
        try:
            with console.status("preparing session..."):
                chat_session = get_chat_session()
            run_agent_loop(chat_session,debug_prompt)
            console.print()
            start_chat_session(chat_session)
        except KeyboardInterrupt:
            console.print()
            console.rule("Chat closed")
            raise typer.Exit(1)

@app.command()
def commit():
    """
    Create an automated Git commit for staged changes.
    
    Ensures that you have changes currently staged (using git add), automatically
    analyzes the staged diff to generate a neat, lowercase commit message,
    and prompts you for confirmation before executing the commit.
    """
    
    # 1. Check for staged files
    console.print("Capturing the staged changes...")
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
    if result.returncode == 0:
        console.print("[yellow]No staged changes found. Please stage files before committing.[/yellow]")
        return

    diff_output = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True).stdout
    debug_prompt = f"Generate commit message based on the given diff, commit and push the code. Give main priority to the project related git preferences while performing git operations.\n\nDiff:\n{diff_output}"
    try:
        with console.status("preparing session..."):
            chat_session = get_chat_session()
        run_agent_loop(chat_session,debug_prompt)
        console.print()
        start_chat_session(chat_session)
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

@app.command()
def model():
    """
    Select and switch the active Gemini model.
    
    Prompts you with an interactive selection of available Gemini models
    (e.g., gemini-3.5-flash, gemini-3.1-pro-preview) and saves your choice
    globally for future commands and chat sessions.
    """
    active_model = get_active_llm_model()
    console.print(f"[magenta]Active Model: [/magenta][dim]{active_model}[/dim]")
    model = questionary.select("Select the model:",choices=["gemini-3.5-flash","gemini-3.1-flash-lite","gemini-3.1-pro-preview","gemini-3-flash-preview"]).ask()
    if model:
        update_llm_model(model)

@app.command()
def report():
    """
    Generate professional project progress reports.
    
    Asks you to select a time frame (e.g., Week, Month, Year) and compiles
    a structured progress summary detailing commits, changes, and features 
    implemented during that period, then starts an interactive chat with the report context.
    """
    time_period = questionary.select("Select time period:",choices=["Week","Month","3 Months","6 Months","Year"]).ask()
    REPORT_PROMPT = read_prompt_from_file("prompts/report_prompt.txt")
    try:
        with console.status("preparing session..."):
            chat_session = get_chat_session()
        run_agent_loop(chat_session,REPORT_PROMPT.replace("{timeperiod}",time_period))
        console.print()
        start_chat_session(chat_session)
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

@app.command()
def eval():
    """Runs the autonomous evaluation suite to verify Raven's patching accuracy."""
    from agent.evals import run_eval_suite
    run_eval_suite()

@app.command()
def tui():
    """
    Launch the multi-modal Textual UI.
    """
    from agent.tui import RavenTUI
    try:
        tui_app = RavenTUI()
        tui_app.run()
    except Exception as e:
        console.print(f"[red]Error launching TUI: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()