import os
import re
import signal
import subprocess
import threading
from datetime import datetime

MAX_COMMAND_OUTPUT_CHARS = 6000
MAX_COMMAND_OUTPUT_LINES = 120
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120

active_sync_process: subprocess.Popen | None = None
_sync_process_cancelled: bool = False
process_lock = threading.Lock()


def set_active_sync_process(proc: subprocess.Popen | None) -> None:
    """Registers or clears the currently running synchronous subprocess."""
    global active_sync_process, _sync_process_cancelled
    with process_lock:
        active_sync_process = proc
        if proc is not None:
            _sync_process_cancelled = False


def was_sync_process_cancelled() -> bool:
    """Returns True if the active synchronous subprocess was cancelled by the user."""
    with process_lock:
        return _sync_process_cancelled


def kill_active_sync_process() -> bool:
    """Forcefully terminates the currently executing synchronous subprocess tree if any."""
    global active_sync_process, _sync_process_cancelled
    with process_lock:
        proc = active_sync_process
        if proc is None or proc.poll() is not None:
            active_sync_process = None
            return False
        _sync_process_cancelled = True
        pid = proc.pid
        active_sync_process = None

    try:
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            try:
                subprocess.Popen(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    except Exception:
        pass
    return True

ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
ANSI_OSC_RE = re.compile(r'\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)')
ORPHAN_ANSI_FRAGMENT_RE = re.compile(r'(?:^|\s|\x1b)(?:;\d+)+(?:;\d+)*m')
CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

def sanitize_command(command: str) -> str:
    """
    Sanitizes commands for safe Windows/PowerShell execution by disabling
    interactive host progress bars and prompts.
    """
    if not command:
        return command
    stripped = command.strip()
    lower = stripped.lower()
    
    # If invoking PowerShell explicitly, ensure silent progress and non-interactive execution
    if lower.startswith("powershell") or lower.startswith("pwsh"):
        if "$progresspreference" not in lower:
            # Check if command has -command or -c
            if re.search(r'-(?:command|c)\s+', lower):
                command = re.sub(
                    r'(?i)(-(?:command|c)\s+)(["\']?)(.*)',
                    r"\1\2$ProgressPreference = 'SilentlyContinue'; \3",
                    command,
                    count=1
                )
            else:
                command = f"{command} -NoProfile -NonInteractive -ExecutionPolicy Bypass"
    return command

def strip_ansi(text: str) -> str:
    """Removes ANSI escape codes, OSC sequences, control characters, and cleans carriage returns from terminal output."""
    if not text:
        return text
    # Remove OSC codes: ESC ] ... (BEL or ESC \)
    text = ANSI_OSC_RE.sub('', text)
    # Remove standard ANSI/CSI escape sequences
    text = ANSI_ESCAPE_RE.sub('', text)
    # Remove orphan ANSI fragment leftovers (e.g. ;30;30m)
    text = ORPHAN_ANSI_FRAGMENT_RE.sub('', text)
    # Remove raw control characters except \n, \r, \t
    text = CONTROL_CHARS_RE.sub('', text)
    # Normalize carriage returns that overwrite terminal lines
    text = re.sub(r'\r\n?', '\n', text)
    return text

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
        # Sanitize command to suppress interactive UI/progress
        cmd_to_run = sanitize_command(command)

        # Prepare environment disabling ANSI colors in test runners/CLI tools
        env = dict(os.environ)
        env["NO_COLOR"] = "1"
        env["FORCE_COLOR"] = "0"
        env["TERM"] = "dumb"

        creationflags = 0
        if os.name == 'nt':
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)

        # Run the command with strict timeout, process tracking, and no shared console buffer
        proc = subprocess.Popen(
            cmd_to_run,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=creationflags,
            start_new_session=(os.name != "nt"),
        )
        set_active_sync_process(proc)
        try:
            stdout_raw, stderr_raw = proc.communicate(timeout=DEFAULT_COMMAND_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            kill_active_sync_process()
            try:
                proc.communicate(timeout=2)
            except Exception:
                pass
            return f"Execution Error: Command timed out after {DEFAULT_COMMAND_TIMEOUT_SECONDS}s. If this is a long-running process, background server, or file download, please use 'start_background_process' instead."
        finally:
            set_active_sync_process(None)

        if was_sync_process_cancelled():
            return "Command execution cancelled by user."

        output = f"Exit Code: {proc.returncode}\n"
        if stdout_raw:
            stdout_clean = strip_ansi(stdout_raw)
            output += f"STDOUT:\n{truncate_output(stdout_clean)}\n"
        if stderr_raw:
            stderr_clean = strip_ansi(stderr_raw)
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
