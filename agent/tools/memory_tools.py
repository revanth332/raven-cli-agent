from pathlib import Path
import os
from agent.utils import get_project_root,get_active_project_name

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
