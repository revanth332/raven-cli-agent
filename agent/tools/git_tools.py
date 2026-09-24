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

def get_staged_git_changes(max_lines: int = 500) -> str:
    """
    Use this tool to retrieve the current staged git changes.

    Args:
        max_lines: Maximum number of diff lines to return to avoid context blowup. Defaults to 500.
    Returns:
        Staged git diff output string or status/error message.
    """
    try:
        command = [
            "git", "diff", "--cached",
            "--",
            ".",
            ":(exclude)*lock*",
            ":(exclude)*.min.*",
            ":(exclude)node_modules/*",
            ":(exclude)dist/*",
            ":(exclude)build/*"
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return f"Failed to get staged git changes: {result.stderr.strip()}"

        diff_output = (result.stdout or "").strip()
        if not diff_output:
            # Fallback check without exclusions in case only lockfiles or excluded files were staged
            fallback = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if fallback.returncode == 0 and fallback.stdout.strip():
                diff_output = fallback.stdout.strip()
            else:
                return "No staged changes found. Please stage files before committing."

        lines = diff_output.splitlines()
        if len(lines) > max_lines:
            truncated_diff = "\n".join(lines[:max_lines])
            return f"{truncated_diff}\n\n[Diff truncated. Showing {max_lines} of {len(lines)} total lines to protect context window.]"

        return diff_output
    except Exception as e:
        return f"Failed to get staged git changes: {e}"

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
    except Exception as e:
        return f"Failed to commit: {e}"

def get_git_log(
    author: str = None,
    since: str = "7 days ago",
    until: str = None,
    max_commits: int = 20,
    include_stat: bool = True,
    path_filter: str = None
) -> str:
    """
    Retrieve structured, compact git commit history within a date range without blowing up context.

    Args:
        author: Optional author name or email substring to filter commits.
        since: Relative or absolute start time (e.g. '7 days ago', '2 weeks ago', '2025-01-01'). Defaults to '7 days ago'.
        until: Optional relative or absolute end time (e.g. 'today', '2025-01-01').
        max_commits: Maximum number of commits to retrieve (defaults to 20, capped at 50).
        include_stat: If True, includes concise file change metrics (--stat) while excluding noisy lockfiles. Defaults to True.
        path_filter: Optional specific file path or directory to filter commits for.
    Returns:
        Formatted commit history string or error message.
    """
    try:
        safe_max = min(max(1, max_commits), 50)
        command = [
            "git", "log",
            "--branches",
            "--pretty=format:%h - %an, %ad : %s",
            "--date=short",
            "-n", str(safe_max)
        ]

        if since:
            command.append(f"--since={since}")
        if until:
            command.append(f"--until={until}")
        if author:
            command.append(f"--author={author}")

        if include_stat:
            command.append("--stat")
        else:
            command.append("--name-status")

        # Exclude noisy lockfiles and build outputs
        command.append("--")
        if path_filter:
            command.append(path_filter)
        else:
            command.append(".")

        command.extend([
            ":(exclude)*lock*",
            ":(exclude)*.min.*",
            ":(exclude)node_modules/*",
            ":(exclude)dist/*",
            ":(exclude)build/*"
        ])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            return f"Failed to get git log: {result.stderr.strip()}"

        output = (result.stdout or "").strip()
        if not output:
            return f"No commits found for the specified criteria (since: {since}, author: {author or 'any'})."

        return output
    except Exception as e:
        return f"Failed to get git log: {e}"