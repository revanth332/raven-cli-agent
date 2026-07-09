from pathlib import Path
import os
import subprocess
from datetime import datetime
import shutil
import time
import json
import tempfile
from playwright.sync_api import sync_playwright


_files_backed_up_this_turn = set()

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
    """ 
    Determines the actual project root by walking up the directory tree and 
    looking for project markers (.git, package.json, etc.).
    Returns the name of the root folder.
    """
    current_dir = Path.cwd()
    root_markers = {'.git', 'package.json', 'pyproject.toml', 'requirements.txt'}
    for directory in [current_dir,*current_dir.parents]:
        if any((directory / marker).exists() for marker in root_markers):
            return directory.name
    return ""

def get_project_root() -> Path:
    """Returns the Path object for the root of the project."""
    current_dir = Path.cwd()
    root_markers = {'.git', 'package.json', 'pyproject.toml', 'requirements.txt'}
    
    for directory in [current_dir, *current_dir.parents]:
        if any((directory / marker).exists() for marker in root_markers):
            return directory
    return current_dir

def update_architecture_map(mermaid_code: str, explanation: str):
    """
    Creates or updates the architecture.md file with a Mermaid.js diagram of the project.
    Args:
        mermaid_code: The raw Mermaid.js graph code (e.g., 'graph TD\n A-->B'). Do not include markdown backticks.
        explanation: A brief text explanation of the architecture.
    """
    try:
        active_dir = get_project_root()
        if not active_dir:
            return "No active project directory found."
        archtecture_file = active_dir / 'architecture.md'
        content = f"Project architecture:\n\n {explanation} \n\n ```mermaid\n{mermaid_code}\n```\n"
        archtecture_file.write_text(content,'utf-8')
        return f"Successfully generated architecture map at {archtecture_file.name}."
    except Exception as e:
        return f"Failed to update architecture map: {e}"

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
    project_name = get_active_project_name()
    if not project_name:
        return ""
    project_name += ".md"
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
    if not project_name:
        return "No active project found. Should save to global memory."
    project_file = Path.home() / ".raven" / "projects" / f"{project_name}.md"
    try:
        with open(project_file, "a", encoding="utf-8") as f:
            f.write(f"\n- {fact}")
        return f"Fact successfully saved to the '{project_name}' project memory."
    except FileNotFoundError:
        return f"Error: File not found at {project_file}."
    except Exception as e:
        return f"An unexpected error occurred while reading '{project_file}': {e}"
        
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
    if not project_name:
        log_entry = f"\n## Error: {error_description}\n- **Solution**: {solution}\n"
    
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

def start_new_backup_turn():
    """
    Called every time the user hits Enter. Resets the backup tracker.
    """
    global _files_backed_up_this_turn
    _files_backed_up_this_turn.clear()

    registry_path = Path.home() / ".raven" / "backups" / "undo_registry.json"
    registry_path.parent.mkdir(parents=True,exist_ok=True)
    registry_path.write_text("[]",encoding="utf-8")

def backup_file(file_path:str):
    """
    Creates a backup file from the file path ONLY IF it hasn't been backed up yet this turn.
    """
    global _files_backed_up_this_turn
    try:
        original_file = Path(file_path)
        if not original_file.exists():
            return
        if str(original_file) in _files_backed_up_this_turn:
            return
        backup_dir = Path.home() / ".raven" / "backups"
        backup_dir.mkdir(parents=True,exist_ok=True)

        safe_name = f"{original_file.name}_{int(time.time())}"
        backup_file = backup_dir / safe_name

        shutil.copy2(original_file,backup_file)

        registry_file = backup_dir / "undo_registry.json"
        try:
            registry = json.loads(registry_file.read_text(encoding='utf-8'))
        except:
            registry = []
        registry.append({
            "original":str(original_file),
            "backup":str(backup_file)
        })
        
        registry_file.write_text(json.dumps(registry),encoding='utf-8')
        _files_backed_up_this_turn.add(str(original_file))
    except Exception as e:
        print(f"Failed to backup the file: {e}")

def patch_file(file_path:str,search_block:str,replace_block:str):
    """
    Use this tool to safely edit a file by replacing an exact, unique block of existing text with new text.
    Args:
        file_path: The relative or absolute path of the file to edit.
        search_block: The exact existing block of text in the file that needs to be replaced.
        replace_block: The new text block that will replace the search_block.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist."
        
        content = path.read_text(encoding='utf-8')

        content_norm = content.replace("\r\n","\n")
        search_block_norm = search_block.replace("\r\n","\n")
        replace_block_norm = replace_block.replace("\r\n","\n")

        occurrences = content_norm.count(search_block_norm)

        if occurrences == 0:
            return f"Error: Could not find the exact text block you wanted to replace in '{file_path}'."
        if occurrences > 1:
            return f"Error: The search_block matches {occurrences} locations in '{file_path}'. Please provide more surrounding lines to make it unique."
        
        backup_file(file_path)

        updated_content = content_norm.replace(search_block_norm,replace_block_norm)
        path.write_text(updated_content,encoding='utf-8')
        return f"Successfully updated '{file_path}'."
        
    except Exception as e:
        return f"Failed to patch file '{file_path}': {e}"

def find_file(file_path:str):
    """
    Use this tool to search for a specific file in the current project directory.
    Args:
        file_path: The exact name of the file to search for.
    Returns:
        A list of matching filepaths, or a message saying no matches were found.
    """
    IGNORE_DIRS = {'node_modules', '.git', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build'}
    matches = []
    for root,dirs,files in os.walk("."):
        # Filter directories dynamically to skip standard ignored folders and any custom venvs
        dirs[:] = [
            d for d in dirs 
            if d not in IGNORE_DIRS and not (Path(root) / d / "pyvenv.cfg").exists()
        ]

        if file_path in files:
            matches.append(Path(root) / file_path)

    if not matches:
        return f"File '{file_path}' not found."
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
    
def get_current_timestamp():
    """
    Use this tool to get the exact current timestamp.
    Returns:
        current timestamp
    """
    now = datetime.now()
    timestamp = now.isoformat(sep='T', timespec='seconds')
    return timestamp

def get_repo_map(max_files: int = 250):
    """
    Get the full repo strucure
    """
    IGNORE_DIRS = {'node_modules', '.git', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build'}
    IGNORE_EXTS = {
        '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.dylib',
        '.mp4', '.mp3', '.wav', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.iso',
        '.env'
    }
    active_project = get_active_project_name()
    if not active_project:
        return ""
    file_paths = []
    for root,dirs,files in os.walk("."):
        # Skip standard ignore dirs and dynamically detect/skip custom virtual environments
        dirs[:] = [
            d for d in dirs 
            if d not in IGNORE_DIRS and not (Path(root) / d / "pyvenv.cfg").exists()
        ]
        for file in files:
            if any(file.lower().endswith(ext) for ext in IGNORE_EXTS):
                continue
            path = Path(root) / file
            file_paths.append(path.as_posix())

            if len(file_paths) >= max_files:
                file_paths.append(f"\n... (Output truncated: reached {max_files} file limit. Directory is too large. Use `find_file` tool to locate specific files.)")
                return "\n".join(file_paths)
    if not file_paths:
        return "No files found in the current directory"

    return "\n".join(file_paths)

def delete_file(file_path: str) -> str:

    """
    Deletes a file at the specified path.
    Args:
        file_path: The path of the file to delete.
    Returns:
        A success or error message.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist."
        
        path.unlink() # Delete the file
        return f"Successfully deleted file '{file_path}'."
    except Exception as e:
        return f"Error deleting file '{file_path}': {e}"

def update_llm_model(model:str):
    """
    Updates the agent configurations like model etc.,
    """
    config_file = Path.home() / ".raven" / "config.json"
    config = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error updaing the model config: {e}")
        config["model"] = model
    else:
        config = {"model":model}
    config_file.write_text(json.dumps(config),encoding='utf-8')

def get_llm_config():
    """
    Provides the LLM configurations like model etc.,
    """
    config_file = Path.home() / ".raven" / "config.json"
    try:
        config = json.loads(config_file.read_text(encoding='utf-8'))
        return config
    except:
        print("Error Loading the model config")
        return {}

def run_ui_test(test_script: str) -> str:
    """
    Executes a Playwright Python script to perform UI automation, scraping, or E2E testing.
    Args:
        test_script: The complete, runnable Python code using the Playwright sync API.
    Returns:
        The standard output and standard error from the test script execution.
    """
    # Create a temporary python file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as temp_file:
        # Prepend the necessary playwright imports in case Raven forgets them
        boiler_plate = """from playwright.sync_api import sync_playwright\nimport sys\n\n"""
        temp_file.write(boiler_plate + test_script)
        temp_file_path = temp_file.name

    try:
        # Run the script using the existing execute_command function we built earlier!
        # Make sure execute_command is imported in this file, or just use subprocess here.
        import subprocess
        result = subprocess.run(
            f"python {temp_file_path}", 
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
    finally:
        # Clean up the temporary file so we don't clutter the user's hard drive
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)