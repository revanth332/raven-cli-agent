from pathlib import Path
import os
import fnmatch
from agent.utils import backup_file

def is_sensitive_file(file_path: str) -> bool:
    """
    Check if a file path points to a sensitive file (e.g., secrets, credentials, env files).
    """
    if not file_path:
        return False
    path = Path(file_path)
    name_lower = path.name.lower()

    # Check for .env files (.env, .env.local, .env.production, something.env, .envrc)
    if name_lower == ".env" or name_lower.startswith(".env") or name_lower.endswith(".env"):
        return True

    # Check sensitive credential and key extensions
    sensitive_file_exts = {".pem", ".key", ".pkcs12", ".pfx", ".keystore"}
    if any(name_lower.endswith(ext) for ext in sensitive_file_exts):
        return True

    # Check SSH private keys
    ssh_keys = {"id_rsa", "id_ecdsa", "id_ed25519", "id_dsa"}
    if name_lower in ssh_keys:
        return True

    # Check path segments
    for part in path.parts:
        part_lower = part.lower()
        if part_lower == ".env" or part_lower.startswith(".env") or part_lower.endswith(".env"):
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

def find_file(file_name: str, max_results: int = 50) -> str:
    """
    Use this tool to search for a specific file in the current project directory.
    Accepts simple filenames (e.g., 'auth.py'), relative/partial paths (e.g., 'security/auth.py'),
    or glob patterns (e.g., '*.py', 'test_*.py', 'skills/*.md').
    Args:
        file_name: The file name, exact partial relative path, or glob pattern to search for.
        max_results: Maximum number of matches to return (defaults to 50).
    Returns:
        A list of matching filepaths, or a message saying no matches were found.
    """
    if not file_name or not file_name.strip():
        return "Error: file_name cannot be empty."

    raw_query = file_name.strip()
    norm_query = raw_query.replace("\\", "/").rstrip("/")
    if norm_query.startswith("./"):
        norm_query = norm_query[2:]

    if is_sensitive_file(raw_query) or is_sensitive_file(norm_query):
        return f"ACCESS DENIED for {raw_query}. Reason: SENSITIVE FILE."

    has_wildcard = any(c in norm_query for c in "*?[]")
    query_lower = norm_query.lower()
    query_is_path = "/" in norm_query

    IGNORE_DIRS = {
        'node_modules', '.git', 'venv', '.env', '.venv', 'env', '__pycache__',
        'dist', 'build', '.pytest_cache', '.mypy_cache', '.ruff_cache',
        '.turbo', '.next', '.nuxt', '.cache', '.idea', '.vscode', '.vs',
        '.coverage', 'htmlcov'
    }
    IGNORE_EXTS = {'.pyc', '.pyo', '.pyd'}

    matches = {}

    for root, dirs, files in os.walk("."):
        # Filter directories dynamically to skip standard ignored folders and any custom venvs
        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS
            and not d.endswith(".egg-info")
            and not (("venv" in d.lower() or d.lower() == "env") and (Path(root) / d / "pyvenv.cfg").exists())
        ]

        for file in files:
            f_lower = file.lower()
            if any(f_lower.endswith(ext) for ext in IGNORE_EXTS):
                continue

            try:
                rel_path = Path(os.path.join(root, file)).relative_to(".").as_posix()
            except ValueError:
                rel_path = (Path(root) / file).as_posix().lstrip("./")

            # Always reject sensitive files during traversal
            if is_sensitive_file(rel_path):
                continue

            rel_lower = rel_path.lower()
            file_stem_lower = Path(file).stem.lower()

            rank = None
            if not has_wildcard:
                if f_lower == query_lower:
                    rank = 0
                elif rel_lower == query_lower:
                    rank = 1
                elif rel_lower.endswith("/" + query_lower):
                    rank = 2
                elif file_stem_lower == query_lower or (query_is_path and rel_lower.endswith("/" + query_lower)):
                    rank = 3
                elif query_lower in f_lower:
                    rank = 6
                elif query_lower in rel_lower:
                    rank = 7
            else:
                if query_is_path:
                    if fnmatch.fnmatchcase(rel_lower, query_lower):
                        rank = 4
                else:
                    if fnmatch.fnmatchcase(f_lower, query_lower):
                        rank = 4
                    elif fnmatch.fnmatchcase(rel_lower, query_lower):
                        rank = 5

            if rank is not None:
                if rel_path not in matches or rank < matches[rel_path]:
                    matches[rel_path] = rank

    if not matches:
        return f"File '{file_name}' not found."

    sorted_matches = sorted(matches.keys(), key=lambda p: (matches[p], len(p), p))
    return str(sorted_matches[:max_results])

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
    if is_sensitive_file(file_path):
        return f"ACCESS DENIED for {file_path}. Reason: SENSITIVE FILE."
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist."
        
        path.unlink() # Delete the file
        return f"Successfully deleted file '{file_path}'."
    except Exception as e:
        return f"Error deleting file '{file_path}': {e}"
