from pathlib import Path
import os
import re
import fnmatch
from typing import Optional
from agent.utils import backup_file

MAX_UNPAGINATED_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

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

def read_file(
    file_path: str,
    start_line: int = 1,
    line_count: int = 250,
    include_line_numbers: bool = True,
) -> str:
    """
    Use this tool to read the contents of a file with pagination and optional line numbers.
    Args:
        file_path: Full path or relative path of the file that needs to be read.
        start_line: Line number to begin reading from (1-indexed, defaults to 1).
        line_count: Number of lines to return (defaults to 250).
        include_line_numbers: Annotate each returned line with line numbers (defaults to True).
    Returns:
        The content of the file (or chunk), or an error/guardrail message.
    """
    if is_sensitive_file(file_path):
        return f"ACCESS DENIED for {file_path}. Reason: SENSITIVE FILE."
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist."
        if not path.is_file():
            return f"Error: '{file_path}' is not a regular file."

        file_size = path.stat().st_size
        # Guardrail against files larger than 1MB when requesting excessive unpaginated reads
        if file_size > MAX_UNPAGINATED_FILE_SIZE and line_count > 500:
            line_count = 500

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")

        lines = content.splitlines()
        total_lines = len(lines)

        if total_lines == 0:
            return f"[File '{file_path}' is empty]"

        start_idx = max(1, int(start_line))
        if start_idx > total_lines:
            return f"Error: start_line ({start_idx}) exceeds total lines ({total_lines}) in '{file_path}'."

        count = max(1, int(line_count))
        end_idx = min(total_lines, start_idx + count - 1)

        selected_lines = lines[start_idx - 1 : end_idx]

        if include_line_numbers:
            pad_width = max(4, len(str(end_idx)))
            formatted_lines = [
                f"{line_num:>{pad_width}} | {line}"
                for line_num, line in enumerate(selected_lines, start=start_idx)
            ]
        else:
            formatted_lines = selected_lines

        output_text = "\n".join(formatted_lines)

        if end_idx < total_lines:
            output_text += (
                f"\n\n[Showing lines {start_idx}-{end_idx} of {total_lines:,}. "
                f"Use start_line={end_idx + 1} to read further]"
            )

        return output_text
    except FileNotFoundError as e:
        return f"File '{file_path}' not found. Error: {e}"
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"


def search_file_content(
    query: str,
    file_path: Optional[str] = None,
    max_matches: int = 20,
    context_lines: int = 2,
) -> str:
    """
    Use this tool to search for regex patterns or literal strings across files in the workspace or in a specific file/directory.
    Args:
        query: Regex pattern or literal string to search for.
        file_path: Target specific file or directory path. If omitted or None, searches across the project workspace.
        max_matches: Maximum matching occurrences to return with context lines (defaults to 20).
        context_lines: Number of surrounding context lines to include before and after matches (defaults to 2).
    Returns:
        Structured search matches with line numbers and context, or a notice if no matches were found.
    """
    if not query or not query.strip():
        return "Error: query cannot be empty."

    raw_query = query.strip()
    try:
        pattern = re.compile(raw_query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(raw_query), re.IGNORECASE)

    max_matches = max(1, int(max_matches))
    context_lines = max(0, int(context_lines))

    IGNORE_DIRS = {
        'node_modules', '.git', 'venv', '.env', '.venv', 'env', '__pycache__',
        'dist', 'build', '.pytest_cache', '.mypy_cache', '.ruff_cache',
        '.turbo', '.next', '.nuxt', '.cache', '.idea', '.vscode', '.vs',
        '.coverage', 'htmlcov'
    }
    IGNORE_EXTS = {
        '.pyc', '.pyo', '.pyd', '.png', '.jpg', '.jpeg', '.gif', '.ico',
        '.pdf', '.zip', '.tar', '.gz', '.7z', '.exe', '.dll', '.so', '.dylib',
        '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.mov'
    }

    files_to_search: list[Path] = []

    if file_path and file_path.strip():
        target = Path(file_path.strip())
        if is_sensitive_file(str(target)):
            return f"ACCESS DENIED for {file_path}. Reason: SENSITIVE FILE."
        if not target.exists():
            return f"Error: Path '{file_path}' does not exist."

        if target.is_file():
            files_to_search.append(target)
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [
                    d for d in dirs
                    if d not in IGNORE_DIRS
                    and not d.endswith(".egg-info")
                    and not (("venv" in d.lower() or d.lower() == "env") and (Path(root) / d / "pyvenv.cfg").exists())
                ]
                for file in files:
                    p = Path(root) / file
                    if p.suffix.lower() in IGNORE_EXTS or is_sensitive_file(str(p)):
                        continue
                    files_to_search.append(p)
    else:
        for root, dirs, files in os.walk("."):
            dirs[:] = [
                d for d in dirs
                if d not in IGNORE_DIRS
                and not d.endswith(".egg-info")
                and not (("venv" in d.lower() or d.lower() == "env") and (Path(root) / d / "pyvenv.cfg").exists())
            ]
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() in IGNORE_EXTS or is_sensitive_file(str(p)):
                    continue
                files_to_search.append(p)

    total_matches = 0
    results_by_file: list[str] = []

    for path in files_to_search:
        if total_matches >= max_matches:
            break

        try:
            if path.stat().st_size > MAX_UNPAGINATED_FILE_SIZE:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            lines = content.splitlines()
            if not lines:
                continue

            matching_indices = [
                idx for idx, line in enumerate(lines)
                if pattern.search(line)
            ]

            if not matching_indices:
                continue

            ranges: list[tuple[int, int]] = []
            for m_idx in matching_indices:
                if total_matches >= max_matches:
                    break
                total_matches += 1
                r_start = max(0, m_idx - context_lines)
                r_end = min(len(lines), m_idx + context_lines + 1)
                if not ranges:
                    ranges.append((r_start, r_end))
                else:
                    prev_start, prev_end = ranges[-1]
                    if r_start <= prev_end:
                        ranges[-1] = (prev_start, max(prev_end, r_end))
                    else:
                        ranges.append((r_start, r_end))

            match_set = set(matching_indices)
            try:
                rel_path = path.relative_to(".").as_posix()
            except ValueError:
                rel_path = path.as_posix()

            file_output = [f"--- {rel_path} ---"]
            for r_start, r_end in ranges:
                pad_width = max(4, len(str(r_end)))
                for line_no in range(r_start + 1, r_end + 1):
                    line_content = lines[line_no - 1]
                    marker = ">" if (line_no - 1) in match_set else " "
                    file_output.append(f"{marker} {line_no:>{pad_width}} | {line_content}")
                file_output.append("...")

            if file_output[-1] == "...":
                file_output.pop()

            results_by_file.append("\n".join(file_output))

        except Exception:
            continue

    if not results_by_file:
        return f"No matches found for '{query}'."

    final_result = "\n\n".join(results_by_file)
    if total_matches >= max_matches:
        final_result += f"\n\n[Showing first {max_matches} matches. Narrow your query or specify a file_path for more specific results.]"

    return final_result
    
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
