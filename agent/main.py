import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.live import Live
from rich.markdown import Markdown
from agent.llm import get_response,get_chat_session,get_streaming_response
from agent.utils import read_prompt_from_file

import sys
import subprocess
import json
from pathlib import Path

app = typer.Typer()
console = Console()

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


def find_and_read_file(filename:str):
    """Returns a tuple of (filepath, content) or (None, None)"""
    matches = list(Path(".").rglob(filename))
    if not matches:
        return None, None
    if len(matches) > 1:
        console.print(f"[yellow]Warning: Found {len(matches)} files named '{filename}'. Using {matches[0]}[/yellow]")

    print(matches)
    chosen_file = matches[0]
    try:
        content = chosen_file.read_text()
        return str(chosen_file),content
    except Exception as e:
        console.print(f"[red]Failed to read the file: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def test():
    print("testng..")

@app.command()
def ask(query:str,file:str = typer.Option(None,"--file","-f")):
    final_query = query
    if file:
        _,content = find_and_read_file(file)
        final_query += "\n\nFile Content: \n\n" + content
    # render_stream(get_streaming_response(final_query))

@app.command()
def chat():
    try:
        with console.status("preparing session..."):
            chat_session = get_chat_session()
        display_welcome()
        while (query := console.input("[green]You:[/] ")) != "exit":
            render_stream(chat_session.send_message_stream(query))
            console.print()
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

@app.command()
def debug():
    DEBUG_PROMPT = read_prompt_from_file("agent/prompts/debug_prompt.txt")
    if sys.stdin.isatty():
        console.print("[red]No input detected. Usage: type error.log | reva debug[/red]")
        raise typer.Exit(1)
    else:
        piped_logs = sys.stdin.read()
        debug_prompt = f"{DEBUG_PROMPT}\n\n{piped_logs}"
        with console.status("debugging..."):
            response = get_response(debug_prompt)
        console.print()
        console.print(Markdown(response))

@app.command()
def commit():
    COMMIT_PROMPT = read_prompt_from_file("agent/prompts/commit_prompt.txt")
    result = subprocess.run(["git","diff","--staged"],capture_output=True,text=True)
    staged_changes = result.stdout.strip()
    if not staged_changes:
        console.print("[yellow]No staged changes found. Please run 'git add' first.[/yellow]")
        raise typer.Exit(1)
    
    commit_genration_prompt = f"{COMMIT_PROMPT} \n\n{staged_changes}"
    with console.status("generating commit message..."):
        commit_message = get_response(commit_genration_prompt)
    console.print(f"[green]{commit_message}[/green]")

    is_user_confirmed = typer.confirm("Commit with this message?")
    if is_user_confirmed:
        subprocess.run(["git","commit","-m",commit_message])
        console.print("[green]✔ commited the code successfully[green]")
    else:
        console.print("[yellow]commit aborted[/yellow]")

@app.command()
def run(instruction:str):
    CMD_PROMPT = read_prompt_from_file("agent/prompts/cmd_prompt.txt")
    command_generation_prompt = f"""{CMD_PROMPT}\n\n {instruction}"""
    try:
        with console.status("generating command..."):
            command_info = get_response(command_generation_prompt)
            command_info_json = json.loads(command_info.strip().replace("```json", "").replace("```", ""))
        command = command_info_json.get('command', 'NONE').strip()
        description = command_info_json.get('description', '')
        if command == "NONE":
            console.print(f"[yellow]{description}[/yellow]")
            return

        console.print(f"[bold cyan]{command}[/bold cyan]")
        console.print(f"Info: {description}")
        should_execute_command = typer.confirm("Execute this command?")
        if should_execute_command:
            subprocess.run(command,shell=True)
        else:
            console.print("[yellow]Command execution termiated[/yellow]")
    except json.JSONDecodeError:
        console.print("[red]Error: The AI did not return a valid command format.[/red]")
        console.print(f"[dim]Raw output: {command_info}[/dim]")
    except Exception as e:
        console.print(f"[red]{e}[/red]")

if __name__ == "__main__":
    app()