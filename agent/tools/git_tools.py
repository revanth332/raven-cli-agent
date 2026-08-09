import subprocess

def get_git_status():
    """
    Use this tool to get the current status of the git repository (staged, unstaged, and untracked files).
    """
    try:
        result = subprocess.run(["git", "status"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return f"Failed to get git status: {result.stderr.strip()}"
        return result.stdout.strip() or "Git status is clean."
    except Exception as e:
        return f"Failed to get git status: {e}"

def git_add(files: list[str] | str = "."):
    """
    Use this tool to stage files for git commit (git add).

    Args:
        files: List of file paths or a single file path/pattern to stage (e.g. ['.'] or ['file.py']). Defaults to '.'.
    Returns:
        Success or error message regarding the git add operation.
    """
    try:
        if isinstance(files, str):
            file_list = [files]
        elif isinstance(files, list):
            file_list = files
        else:
            file_list = ["."]

        if not file_list:
            file_list = ["."]

        command = ["git", "add"] + file_list
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return f"Failed to stage files: {result.stderr.strip()}"
        return f"Successfully staged files: {', '.join(file_list)}"
    except Exception as e:
        return f"Failed to stage files: {e}"

def get_git_diff(file_path: str = None, staged: bool = False):
    """
    Use this tool to retrieve git diff output.

    Args:
        file_path: Optional path to a specific file to check diff for.
        staged: If True, shows staged changes (--cached). Defaults to False (unstaged working directory changes).
    Returns:
        Diff output string or status message.
    """
    try:
        command = ["git", "diff"]
        if staged:
            command.append("--cached")
        if file_path:
            command.append(file_path)

        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return f"Failed to get git diff: {result.stderr.strip()}"

        diff_output = (result.stdout or "").strip()
        if not diff_output:
            target = f"for '{file_path}'" if file_path else ""
            diff_type = "staged" if staged else "unstaged"
            return f"No {diff_type} changes found {target}.".strip()
        return diff_output
    except Exception as e:
        return f"Failed to get git diff: {e}"

def get_staged_git_changes():
    """
    Use this tool to retrieve the current staged git changes.
    """
    try:
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode == 0:
            return "No staged changes found. Please stage files before committing."
        diff_output = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        return diff_output
    except subprocess.CalledProcessError as e:
        return f"Failed to get the staged changes {e}"

def commit_staged_git_changes(message:str):
    """
    Use this tool to commit the code with a commit message.

    Args:
        message: commit message related to the code changes
    Returns:
        Success or error message regarding the commit operation
    """
    try:
        command = ["git", "commit", "-m", message]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return f"Failed to commit: {result.stderr.strip()}"
        return "Successfully committed the changes"
    except subprocess.CalledProcessError as e:
        return f"Failed to commit: {e}"