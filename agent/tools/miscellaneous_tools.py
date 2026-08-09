import subprocess
from datetime import datetime

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
