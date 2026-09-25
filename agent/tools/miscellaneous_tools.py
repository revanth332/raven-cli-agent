import os
import re
import subprocess
from datetime import datetime

MAX_COMMAND_OUTPUT_CHARS = 6000
MAX_COMMAND_OUTPUT_LINES = 120

ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Removes ANSI escape codes and cleans carriage returns from terminal output."""
    if not text:
        return text
    # Normalize carriage returns that overwrite terminal lines
    text = re.sub(r'\r\n?', '\n', text)
    return ANSI_ESCAPE_RE.sub('', text)

def truncate_output(text: str, max_chars: int = MAX_COMMAND_OUTPUT_CHARS, max_lines: int = MAX_COMMAND_OUTPUT_LINES) -> str:
    """
    Truncates excessive command output to prevent token context explosion.
    Preserves initial lines (head) and trailing lines (tail) with a clear truncation banner.
    """
    if not text:
        return text

    total_chars = len(text)
    lines = text.splitlines()
    total_lines = len(lines)

    if total_lines <= max_lines and total_chars <= max_chars:
        return text

    # If lines exceed max_lines, keep head and tail
    if total_lines > max_lines:
        head_count = int(max_lines * 0.75)
        tail_count = max_lines - head_count
        omitted_lines = total_lines - (head_count + tail_count)

        head_lines = lines[:head_count]
        tail_lines = lines[-tail_count:] if tail_count > 0 else []

        head_text = "\n".join(head_lines)
        tail_text = "\n".join(tail_lines)
        omitted_chars = total_chars - (len(head_text) + len(tail_text))

        banner = f"\n\n... [Output truncated: {omitted_lines} lines / {max(0, omitted_chars)} characters omitted. Please filter your command query] ...\n\n"
        truncated = head_text + banner + tail_text
    else:
        truncated = text

    # If total characters exceed max_chars, truncate characters
    if len(truncated) > max_chars:
        head_chars = int(max_chars * 0.75)
        tail_chars = max_chars - head_chars
        omitted_chars = len(truncated) - (head_chars + tail_chars)
        banner = f"\n\n... [Output truncated: {omitted_chars} characters omitted. Please filter your command query] ...\n\n"
        truncated = truncated[:head_chars] + banner + truncated[-tail_chars:]

    return truncated

def execute_command(command: str) -> str:
    """
    Executes a terminal command (CMD/PowerShell) on the user's Windows machine and returns the output.
    Args:
        command: The exact terminal command to execute.
    Returns:
        The exit code, stdout, and stderr output of the command (safely capped if excessive).
    """
    try:
        # Prepare environment disabling ANSI colors in test runners/CLI tools
        env = dict(os.environ)
        env["NO_COLOR"] = "1"
        env["FORCE_COLOR"] = "0"
        env["TERM"] = "dumb"

        # Run the command, capturing output and ignoring encoding errors on Windows
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding="utf-8", 
            errors="ignore",
            env=env
        )
        
        output = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            stdout_clean = strip_ansi(result.stdout)
            output += f"STDOUT:\n{truncate_output(stdout_clean)}\n"
        if result.stderr:
            stderr_clean = strip_ansi(result.stderr)
            output += f"STDERR:\n{truncate_output(stderr_clean, max_chars=3000, max_lines=60)}\n"
            
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
