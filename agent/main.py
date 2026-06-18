import typer
from rich.console import Console                                                                                                                     
from rich.panel import Panel                                                                                                                         
from rich.text import Text                                                                                                                           
from rich.align import Align
from rich.markdown import Markdown
from agent.llm import get_response,get_chat_session

import sys
import subprocess
import json

app = typer.Typer()
console = Console()

def display_welcome():                                                                                                                                                                                                                         
    reva_text = Text("Raven", style="green")                                                                                                      
                                                                                                                                                     
    # 2. Create the Panel (the box)                                                                                                                                                                                                 
    welcome_panel = Panel(                                                                                                                           
        Align.center(reva_text),                                                                                                                     
        title="[bold white]CLI AGENT[/bold white]",                                                                                                  
        subtitle="[dim]v0.1.0[/dim]",                                                                                                                
        border_style="green",                                                                                                                  
        padding=(1, 10),                                                                                                                             
        expand=False                                                                                                                                 
    )                                                                                                                                                
                                                                                                                                                      
    # 3. Print a little spacing and the panel                                                                                                        
    console.print("\n")                                                                                                                              
    console.print(welcome_panel)                                                                                                                     
    console.print("[dim italic]System ready. How can I help you today?[/dim italic]\n")   

@app.command()
def test():
    print("testng..")

@app.command()
def ask(query:str):
    with console.status("thinking..."):
        response = get_response(query)
    console.print(Markdown(response))

@app.command()
def chat():
    try:
        display_welcome()
        with console.status("preparing session..."):
            chat_session = get_chat_session()
        while (query := console.input("[green]You:[/] ")) != "exit":
            with console.status("thinking..."):
                response = chat_session.send_message(query)
            console.print(Markdown(response.text))
    except KeyboardInterrupt:
        console.print()
        console.rule("Chat closed")
        raise typer.Exit(1)

@app.command()
def debug():
    if sys.stdin.isatty():
        console.print("[red]No input detected. Usage: type error.log | reva debug[/red]")
        raise typer.Exit(1)
    else:
        piped_logs = sys.stdin.read()
        debug_prompt = f"Analyze the following logs/code and explain the error and how to fix it:\n\n{piped_logs}"
        with console.status("debugging..."):
            response = get_response(debug_prompt)
        console.print()
        console.print(Markdown(response))

@app.command()
def commit():
    result = subprocess.run(["git","diff","--staged"],capture_output=True,text=True)
    staged_changes = result.stdout.strip()
    if not staged_changes:
        console.print("[yellow]No staged changes found. Please run 'git add' first.[/yellow]")
        raise typer.Exit(1)
    
    commit_genration_prompt = f"Write a concise, professional, conventional, short git commit message based on the following diff. Only return the commit message, no markdown formatting or extra text. \n\n{staged_changes}"
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
    command_generation_prompt = f"Translate this natural language instruction into a Windows command line command (CMD/PowerShell). Return the response only in given JSON format. FORMAT: {{command:<command> description:<short, precise desciption about the command>}}. MUST resurn pure json. No backticks, no explanation, only pure json. If no command found then return plain text of explanation with details of similar commands. Instruction: {instruction}"
    with console.status("generating command..."):
        command_info = get_response(command_generation_prompt)
        command_info_json = json.dumps(command_info)
    if isinstance(command_info_json,dict):
        command = command_info_json['command']
        console.print(f"[bold cyan]{command}[/bold cyan]")
        should_execute_command = typer.confirm("Execute this command?")
        if should_execute_command:
            subprocess.run(command,shell=True)
        else:
            console.print("[yellow]Command execution termiated[/yellow]")
    else:
        console.print(f"[yellow]{command_info}[/yellow]")

if __name__ == "__main__":
    app()