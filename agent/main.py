import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.live import Live
from rich.markdown import Markdown
from agent.llm import get_response,get_chat_session,get_streaming_response
from agent.utils import read_prompt_from_file,save_to_memory,find_file,read_file,write_file,create_file,execute_command
from google.genai import types

import sys
import os
import subprocess
import json
from pathlib import Path

app = typer.Typer()
console = Console()

TOOL_REGISTRY = {
    "save_to_memory": save_to_memory,
    "find_file":find_file,
    "read_file":read_file,
    "write_file":write_file,
    "create_file":create_file,
    "execute_command":execute_command
}

def display_welcome():
    reva_text = Text("Raven", style="green")
    # 2. Create the Panel (the box)
    welcome_panel = Panel(
        Align.center(reva_text),title="[bold white]CLI AGENT[/bold white]",
        subtitle="[dim]v0.1.0[/dim]",
        border_style="green",
        padding=(1, 10),
        expand=False
    )
    # 3. Print a little spacing and the panel
    console.print("\n")
    console.print(welcome_panel)
    console.print("[dim italic]System ready. How can I help you today?[/dim italic]\n")

def render_stream(generator):
    full_response = ""
    with Live(Markdown(full_response),refresh_per_second=10,console=console) as live:
        for chunk in generator:
            if hasattr(chunk,'text') and chunk.text:
                full_response += chunk.text
            elif isinstance(chunk,str):
                full_response += chunk
            live.update(Markdown(full_response))

def run_agent_loop(chat_session,intial_input):
    """The core multi-turn engine of Raven"""
    current_input = intial_input

    while True:
        final_response = ""
        function_calls = []

        with Live(Markdown(""),refresh_per_second=10,console=console) as live:
            generator = chat_session.send_message_stream(current_input)
            for chunk in generator:
                if hasattr(chunk,'text') and chunk.text:
                    final_response += chunk.text
                if hasattr(chunk,"function_calls") and chunk.function_calls:
                    function_calls.extend(chunk.function_calls)
                live.update(Markdown(final_response))
        if len(function_calls) == 0:
            break
        tool_responses = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = fc.args

            if tool_name == "write_file":
                console.print(f"\n[bold yellow]Raven wants to write to file: {tool_args['file_path']}[/bold yellow]")
                console.print(f"[dim]Proposed Content:\n{tool_args['content']}[/dim]")

                confirmation = typer.confirm("Allow Raven to write this file?")
                if confirmation == False:
                    result = "Error: User denied permission to write to this file."
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result":result}
                        )
                    )
                    continue

            if tool_name == "execute_command":
                console.print(f"\n[bold red]WARNING: Raven wants to execute terminal command: {tool_args['command']}[/bold red]")
                
                confirmed = typer.confirm("Allow Raven to execute this command?")
                if not confirmed:
                    result = "Error: User denied permission to execute this terminal command."
                    tool_responses.append(
                        types.Part.from_function_response(name=tool_name, response={"result": result})
                    )
                    continue
            
            console.print(f"\n[dim italic]Raven is executing: {tool_name}({tool_args})[/dim italic]\n")

            if tool_name in TOOL_REGISTRY:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_args)
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

def find_and_read_file(filename:str):
    """Returns a tuple of (filepath, content) or (None, None)"""
    IGNORE_DIRS = {'node_modules', '.git', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build'}
    matches = []
    for root,dirs,files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        if filename in files:
            matches.append(Path(root) / filename)

    if not matches:
        return None, None
    if len(matches) > 1:
        console.print(f"[yellow]Warning: Found {len(matches)} files named '{filename}'. Using {matches[0]}[/yellow]")

    chosen_file = matches[0]
    try:
        content = chosen_file.read_text(encoding="utf-8")
        return str(chosen_file),content.strip()
    except Exception as e:
        console.print(f"[red]Failed to read the file: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def test():
    print("testng..")

@app.command()
def chat(query:str):
    try:
        with console.status("preparing session..."):
            chat_session = get_chat_session()
        display_welcome()
        if query:
            console.print(f"[green]You:[/] {query}")
            console.print()
            run_agent_loop(chat_session,query)
            console.print()
        while (query := console.input("[green]You:[/] ")) != "exit":
            run_agent_loop(chat_session,query)
            console.print()
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

@app.command()
def debug():
    DEBUG_PROMPT = read_prompt_from_file("prompts/debug_prompt.txt")
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
            while (query := console.input("[green]You:[/] ")) != "exit":
                run_agent_loop(chat_session,query)
                console.print()
        except KeyboardInterrupt:
            console.print()
            console.rule("Chat closed")
            raise typer.Exit(1)

@app.command()
def commit(file:str = typer.Option(None,"--file","-f")):
    COMMIT_PROMPT = read_prompt_from_file("prompts/commit_prompt.txt")
    
    commit_genration_prompt = f"{COMMIT_PROMPT}"
    if file:
        commit_genration_prompt += f"Use only {file} file chnages to generate commit message."
    try:
        with console.status("preparing session..."):
            chat_session = get_chat_session()
        run_agent_loop(chat_session,commit_genration_prompt)
        console.print()
        while (query := console.input("[green]You:[/] ")) != "exit":
            run_agent_loop(chat_session,query)
            console.print()
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()