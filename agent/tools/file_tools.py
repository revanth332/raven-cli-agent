from pathlib import Path
import os
from agent.utils import backup_file

def is_sensitive_file(file_path:str):
    sensitive_file_exts = {".env"}
    if any(file_path.lower().endswith(ext) for ext in sensitive_file_exts):
        return True
    return False

def patch_file(file_path:str,search_block:str,replace_block:str):
    """
    Use this tool to safely edit a file by replacing an exact, unique block of existing text with new text.
    Args:
        file_path: The relative or absolute path of the file to edit.
        search_block: The exact existing block of text in the file that needs to be replaced.
        replace_block: The new text block that will replace the search_block.
    """
    if is_sensitive_file(file_path):
        return f"ACCESS DENIED for {file_path}. Reason: SENSITIVE FILE."
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

def find_file(file_name:str):
    """
    Use this tool to search for a specific file in the current project directory.
    Accepts both simple filenames (e.g., 'auth.py') and relative/partial paths (e.g., 'security/auth.py').
    Args:
        file_name: The file name or exact partial relative path to search for.
    Returns:
        A list of matching filepaths, or a message saying no matches were found.
    """
    IGNORE_DIRS = {'node_modules', '.git', 'venv', '.env', '.venv', '__pycache__', 'dist', 'build'}
    IGNORE_EXTS = {
            '.env'
        }
    if is_sensitive_file(file_name):
        return f"ACCESS DENIED for {file_name}. Reason: SENSITIVE FILE."
    matches = []
    normalized_file_path = Path(file_name).as_posix()
    for root,dirs,files in os.walk("."):
        # Filter directories dynamically to skip standard ignored folders and any custom venvs
        dirs[:] = [
            d for d in dirs 
            if d not in IGNORE_DIRS and not (Path(root) / d / "pyvenv.cfg").exists()
        ]
        for file in files:
            if any(file.lower().endswith(ext) for ext in IGNORE_EXTS):
                continue
            rel_path = Path(root) / file
            rel_path = rel_path.as_posix()
            if not rel_path.endswith(".env") and file == normalized_file_path or rel_path.endswith(normalized_file_path):
                matches.append(rel_path)

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
    if is_sensitive_file(file_path):
        return f"ACCESS DENIED for {file_path}. Reason: SENSITIVE FILE."
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
            return f"Error: File '{file_path}' already exists."
            
        # Ensure parent directories exist before creating the file
        path.parent.mkdir(parents=True, exist_ok=True)
        
        path.write_text(content, encoding="utf-8")
        return f"Successfully created file '{file_path}'."
    except Exception as e:
        return f"Error creating file '{file_path}': {e}"

def delete_file(file_path: str) -> str:

    """
    Deletes a file at the specified path.
    Args:
        file_path: The path of the file to delete.
    Returns:
        A success or error message.
    """
    if is_sensitive_file:
        return f"ACCESS DENIED for {file_path}. Reason: SENSITIVE FILE."
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist."
        
        path.unlink() # Delete the file
        return f"Successfully deleted file '{file_path}'."
    except Exception as e:
        return f"Error deleting file '{file_path}': {e}"
