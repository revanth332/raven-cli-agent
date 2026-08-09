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
from agent.core.llm import get_chat_session
from agent.utils import read_prompt_from_file,start_new_backup_turn
from agent.core.settings import settings
from agent.tools.tool_registry import TOOL_REGISTRY

import sys
from pathlib import Path
import json
import shutil
import subprocess
import time
from typing import List, Optional


app = typer.Typer()
console = Console()

chat_style = Style([
            ('question', 'fg:#06B6D4 bold'),
            ('answer', 'fg:#06B6D4'),
        ])

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
    active_model = settings.RAVEN_MODEL
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

def run_agent_loop(chat_session,intial_input):
    """The core multi-turn engine of Raven"""
    current_input = intial_input
    max_retries = 5
    try:
        while True:
            final_response = ""
            function_calls = {}
            with Live(Spinner("dots", text="Thinking...", style="cyan"),refresh_per_second=10,console=console) as live:
                for attempt in range(max_retries):
                    try:
                        generator = chat_session.send_message_stream(current_input)
                        for chunk in generator:
                            if not chunk.choices:
                                continue
                            delta = chunk.choices[0].delta
                            if delta.tool_calls:
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
                            if delta.content:
                                final_response += delta.content
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
            if not function_calls:
                break
            tool_calls_to_append = []
            tool_responses_to_append = []
            for _,fc in function_calls.items():
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

                elif tool_name == "execute_command":
                    console.print(f"[bold red]• Execute[/bold red]([dim]{tool_args['command']}[/dim])")
                    
                    confirmed = typer.confirm("Allow Raven to execute this command?")
                    if not confirmed:
                        result = "Error: User denied permission to execute this terminal command."
                        tool_responses_to_append.append({
                            "role": "tool",
                            "tool_call_id": fc["id"],
                            "name": fc["name"],
                            "content": result
                        })
                        continue
                
                elif tool_name == "run_ui_test":
                    console.print(f"[bold red]• Browser[/bold red]()")

                    confirmed = typer.confirm("Raven wants to run a UI Automation Script. Allow?")
                    if not confirmed:
                        result = "Error: User denied permission to execute this automation script."
                        tool_responses_to_append.append({
                                                "role": "tool",
                                                "tool_call_id": fc["id"],
                                                "name": fc["name"],
                                                "content": result
                                            })
                        continue

                elif tool_name == "commit_staged_git_changes":
                    console.print(f"[bold cyan]• Commit[/bold cyan]([dim]{tool_args['message']}[/dim]{',[red]unverified[/red]' if not tool_args['is_verified'] else ''})")
                    confirmed = typer.confirm("Raven wants to commit the changes. Allow?")
                    if not confirmed:
                        result = "Error: User denied permission to commit the changes."
                        tool_responses_to_append.append({
                                            "role": "tool",
                                            "tool_call_id": fc["id"],
                                            "name": fc["name"],
                                            "content": result
                                        })
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
            
                tool_responses_to_append.append({
                                            "role": "tool",
                                            "tool_call_id": fc["id"],
                                            "name": fc["name"],
                                            "content": json.dumps(result)
                                        })
            
            chat_session.add_message("assistant",tool_calls=tool_calls_to_append)
            for tool_response in tool_responses_to_append:
                chat_session.add_message(role="tool",tool_call_id=tool_response["tool_call_id"],name=tool_response["name"],content=tool_response["content"])
            current_input = None
    except Exception as e:
        console.print(e)

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
    except Exception as e:
        console.print(f"[red]ERROR: {e}[/]")
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
    DEBUG_PROMPT = read_prompt_from_file("prompts/debug_prompt.md")
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
def config(set_vars: Optional[List[str]] = typer.Option(
    None,"--set","-s",help="Key-value pairs as key=value"
)):
    config = {}
    if set_vars:
        for item in set_vars:
            if "=" not in item:
                typer.echo(f"Invalid format: '{item}'. Use key=value.", err=True)
                raise typer.Exit(1)
            key, val = item.split("=")
            config[key] = val
        try:
            settings.set_config(config)
        except Exception as e:
            typer.echo(f"Failed to set config: {e}", err=True)
            raise typer.Exit(1)
    

@app.command()
def report():
    """
    Generate professional project progress reports.
    
    Asks you to select a time frame (e.g., Week, Month, Year) and compiles
    a structured progress summary detailing commits, changes, and features 
    implemented during that period, then starts an interactive chat with the report context.
    """
    time_period = questionary.select("Select time period:",choices=["Week","Month","3 Months","6 Months","Year"]).ask()
    REPORT_PROMPT = read_prompt_from_file("prompts/report_prompt.md")
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
    from agent.terminal_ui.app import RavenTUI
    try:
        tui_app = RavenTUI()
        tui_app.run()
    except Exception as e:
        console.print(f"[red]Error launching TUI: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()