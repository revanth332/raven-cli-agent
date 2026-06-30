from pathlib import Path
import os
import subprocess

def read_prompt_from_file(path:str):
    """
    Load a prompt from a text file into a single string.
    """
    agent_dir = Path(__file__).parent
    file_path = agent_dir / path
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: Prompt file not found at '{file_path}'. Exiting.")
        exit()
    except Exception as e:
        print(f"An unexpected error occurred while reading '{file_path}': {e}")
        exit()

def get_active_project_name() -> str:
    """Returns the folder name of the current working directory."""
    return os.path.basename(os.getcwd())

def get_memory_content():
    """
    Load Global memory content from the memory file if exists or creates a memory file.
    """
    memory_file = Path.home() / ".raven" / "memory.md"

    if not memory_file.exists():
        memory_file.parent.mkdir(parents=True,exist_ok=True)
        default_memory = "You are Raven, my personal AI developer agent. Here is what you know about me:\n\n- I use Windows.\n- My main stack is React, Node, and Python."
        memory_file.write_text(default_memory,encoding='utf-8')
    return memory_file.read_text(encoding='utf-8')

def get_project_memory():
    """Loads or initializes memory specific to the active project folder."""
    project_name = get_active_project_name() + ".md"
    project_memory_file = Path.home() / ".raven" / "projects" / project_name
    if not project_memory_file.exists():
        project_memory_file.parent.mkdir(parents=True,exist_ok=True)
        default_project_memory = f"# Project Context: {project_name}\n\n- This project is located at {os.getcwd()}\n"
        project_memory_file.write_text(default_project_memory, encoding="utf-8")
    return project_memory_file.read_text(encoding='utf-8')


def save_to_memory(information:str,category:str):
    """
    Use this tool to save important facts, user preferences, project details, or newly learned concepts to long-term memory.
    Call this automatically when the user mentions something that would be useful for future interactions.
    Args:
        information: The exact text or factual insight to be memorized.
        category: The classification for this memory (e.g., 'preference', 'fact').
    """
    memory_file = Path.home() / ".raven" / "memory.md"
    with open(memory_file,'a',encoding='utf-8') as f:
        f.write(f"\n-{category}: {information}")
    return "New data added to memory successfully"

def save_to_project_memory(fact: str) -> str:
    """
    Use this tool to save important facts, context, setup details, or architectural patterns specific to the CURRENT project.
    Args:
        fact: A short, concise fact about the current project to remember.
    """
    project_name = get_active_project_name()
    project_file = Path.home() / ".raven" / "projects" / f"{project_name}.md"
    
    with open(project_file, "a", encoding="utf-8") as f:
        f.write(f"\n- {fact}")
    return f"Fact successfully saved to the '{project_name}' project memory."

def log_successful_debug(error_description: str, solution: str) -> str:
    """
    Logs a successfully resolved error and its detailed solution to global debug history for future reference.
    Args:
        error_description: The error message or description of the issue.
        solution: The exact fix or steps taken to resolve the error.
    """
    debug_file = Path.home() / ".raven" / "debug_history.md"
    
    if not debug_file.exists():
        debug_file.parent.mkdir(parents=True, exist_ok=True)
        debug_file.write_text("# Debugging History & Error Resolutions\n\n", encoding="utf-8")
        
    project_name = get_active_project_name()
    log_entry = f"\n## Error: {error_description}\n- **Project**: {project_name}\n- **Solution**: {solution}\n"
    
    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
    return "Debug session successfully logged in global history."


def save_concept(concept_name: str, explanation: str) -> str:
    """
    Saves a detailed markdown explanation of a concept, design pattern, or architecture that the user is deeply exploring or has high interest in.
    Args:
        concept_name: The name of the concept or technology (e.g. 'React Context API', 'Docker Setup').
        explanation: A precise, organized explanation of the concept in markdown format.
    """
    # Clean filename (e.g., "React Context API" -> "react_context_api.md")
    safe_name = concept_name.lower().replace(" ", "_")
    concept_file = Path.home() / ".raven" / "concepts" / f"{safe_name}.md"
    
    concept_file.parent.mkdir(parents=True, exist_ok=True)
    concept_file.write_text(f"# Concept: {concept_name}\n\n{explanation}\n", encoding="utf-8")
    return f"Concept '{concept_name}' successfully documented."

def find_file(file_name:str):
    """
    Use this tool to search for a specific file in the current project directory.
    Args:
        file_name: The exact name of the file to search for.
    Returns:
        A list of matching filepaths, or a message saying no matches were found.
    """
    IGNORE_DIRS = {'node_modules', '.git', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build'}
    matches = []
    for root,dirs,files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        if file_name in files:
            matches.append(Path(root) / file_name)

    if not matches:
        return f"File '{file_name}' not found."
    return str([str(m) for m in matches])

def read_file(file_path:str):
    """
    Use this tool to read the contents of a file.
    Args:
        file_path: Full path of the file that needs to be read
    Returns:
        The content of the file, or an error message.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError as e:
        return f"File {file_path} not found. Error: {e}"
    except:
        return f"Error reading file '{file_path}': {e}"

def write_file(file_path:str,content:str):
    """
    Use this tool to write cotent into a file.
    Args:
        file_path: Full path of the file
        content: The text content to write into the file.
    """
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return f"Successfully wrote content to '{file_path}'."
    except FileNotFoundError as e:
        return f"File {file_path} not found. Error: {e}"
    except:
        return f"Error while writing into the file: {file_path}"
    
def create_file(file_path: str, content: str = "") -> str:
    """
    Use this tool to create a new file and write initial text content into it.
    Fails safely if the file already exists to prevent accidental overwriting.

    Args:
        file_path: The relative or absolute path of the file to create.
        content: The initial text content to write into the file. Defaults to an empty string.
    Returns:
        A success or error message.
    """
    try:
        path = Path(file_path)
        
        # Guard clause: Prevent wiping out an existing file
        if path.exists():
            return f"Error: File '{file_path}' already exists. Use write_file to overwrite it."
            
        # Ensure parent directories exist before creating the file
        path.parent.mkdir(parents=True, exist_ok=True)
        
        path.write_text(content, encoding="utf-8")
        return f"Successfully created file '{file_path}'."
    except Exception as e:
        return f"Error creating file '{file_path}': {e}"

def execute_command(command: str) -> str:
    """
    Executes a terminal command (CMD/PowerShell) on the user's Windows machine and returns the output.
    Args:
        command: The exact terminal command to execute.
    Returns:
        The exit code, stdout, and stderr output of the command.
    """
    try:
        # Run the command, capturing output and ignoring encoding errors on Windows
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding="utf-8", 
            errors="ignore"
        )
        
        output = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
            
        return output
    except Exception as e:
        return f"Failed to execute command. Error: {e}"