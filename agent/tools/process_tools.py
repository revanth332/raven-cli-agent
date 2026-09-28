import time
from agent.core.process_manager import process_manager

def start_background_process(command: str, process_name: str = "", working_dir: str = "") -> str:
    """
    Starts a background process and returns a formatted string with handle, pid, status, and initial stdout/stderr lines.
    Args:
        command (str): The command to run.
        process_name (str): Optional name for the process.
        working_dir (str): Optional working directory for the process.
    Returns:
        str: Formatted string with handle, pid, status, and initial stdout/stderr lines
    """
    result = process_manager.start_process(command, name=process_name, cwd=working_dir or None)
    if result is None:
        raise RuntimeError("Failed to start the background process.")
    status_str = "running" if result["status"] else "exited"
    return f"Started background process '{result['handle']}' (PID: {result['pid']}). Status: {status_str}.\nInitial Output:\n{result['initial_logs']}"

def check_process_status(handle_or_pid: str, tail_lines: int = 50) -> str:
    """
    Checks the status of a background process by its handle or PID.
    Args:
        handle_or_pid (str): The handle or PID of the process.
        tail_lines (int): Number of log lines to retrieve.
    Returns:
        str: The status and logs of the process.
    """
    bg_process = process_manager.get_process(handle_or_pid)
    if bg_process is None:
        return f"No process found with handle or PID: {handle_or_pid}"
    
    status = "running" if bg_process.is_running else f"exited with code {bg_process.exit_code}"
    logs = bg_process.get_logs(tail_lines=tail_lines)
    
    return f"PID: {bg_process.process.pid} is {status}.\nuptime: {time.time() - bg_process.start_time}\nLogs:\n{logs}"

def stop_background_process(handle_or_pid: str, force: bool = False) -> str:
    """
    Stops a background process by its handle or PID.
    Args:
        handle_or_pid (str): The handle or PID of the process.
        force (bool): Whether to forcefully terminate the process.
    Returns:
        str: Result message indicating success or failure.
    """
    success = process_manager.stop_process(handle_or_pid, force=force)
    if success:
        return f"Process with handle or PID {handle_or_pid} has been stopped."
    else:
        return f"No process found with handle or PID: {handle_or_pid}"

def list_background_processes() -> str:
    """
    Lists all currently managed background processes.
    Returns:
        str: A formatted string listing all processes with their handles, PIDs, and statuses.
    """
    process_list = process_manager.list_processes()
    if not process_list:
        return "No background processes are currently running."
    lines = []
    for p in process_list:
        status = "running" if p["status"] else f"exited ({p['exit_code']})"
        lines.append(f"• [{p['handle']}] (PID {p['pid']}) - '{p['name']}': {status}")
    return "\n".join(lines)