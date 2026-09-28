from dataclasses import dataclass
import subprocess
import time
import os
import atexit
import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional
from agent.tools.miscellaneous_tools import strip_ansi

@dataclass
class BackgroundProcess:
    handle:str
    process: subprocess.Popen
    name:str = ""

    def __post_init__(self) -> None:
        if not self.name: self.name = self.handle
        self.start_time = time.time()
        self.log_buffer = deque(maxlen=200)  # Store the last 200 log lines
        self._lock = threading.Lock()
        self._start_log_reader()

    def _start_log_reader(self):
        def _read_stream(stream):
            for line in iter(stream.readline,''):
                clean_line = strip_ansi(line.rstrip("\r\n"))
                if clean_line:
                    with self._lock:
                        self.log_buffer.append(clean_line)
            stream.close()
        threading.Thread(target=_read_stream,args=(self.process.stdout,),daemon=True).start()
        threading.Thread(target=_read_stream,args=(self.process.stderr,),daemon=True).start()
    
    def get_logs(self,tail_lines:int=10) -> str:
        with self._lock:
            lines = list(self.log_buffer)[-tail_lines:]
        return "\n".join(lines)
    @property
    def is_running(self) -> bool:
        return self.process.poll() is None
    @property
    def exit_code(self) -> Optional[int]:
        return self.process.poll()

class ProcessManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._counter = 0
        self.processes: Dict[str, BackgroundProcess] = {}

    def start_process(self,command:str,name:str="",cwd:Optional[str]=None):
        """
        Spawns a background command with creationflags for Windows process group.
        Waits ~2 seconds to capture immediate output or early crashes, then returns status.
        """
        handle = f"{name}_{self._counter}" if name else f"process_{self._counter}"
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        env = dict(os.environ)
        env["NO_COLOR"] = "1"
        env["FORCE_COLOR"] = "0"
        env["TERM"] = "dumb"
        process = subprocess.Popen(
            command, 
            shell=True, 
            stdin=subprocess.DEVNULL, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            cwd=cwd,
            creationflags=creationflags,
            env=env
        )
        bg_process = BackgroundProcess(handle=handle, process=process, name=name)
        with self._lock:
            self.processes[handle] = bg_process
            self._counter += 1
        time.sleep(2)  # Wait for a moment to capture initial output
        return {"handle":handle,"pid":process.pid,"status":bg_process.is_running,"initial_logs":bg_process.get_logs(tail_lines=10)}
    
    def stop_process(self,handle_or_pid:str,force:bool=False) -> bool:
        """
        Stops a background process by its handle or PID.
        """
        with self._lock:
            bg_process = self.processes.get(handle_or_pid)
            if bg_process is None:
                for proc in self.processes.values():
                    if str(proc.process.pid) == str(handle_or_pid):
                        bg_process = proc
                        break
            if bg_process:
                if os.name == 'nt':
                    # On Windows, console processes (node, python, cmd) ignore WM_CLOSE and require /F
                    subprocess.run(
                        f"taskkill /PID {bg_process.process.pid} /T /F",
                        shell=True,
                        capture_output=True
                    )
                else:
                    bg_process.process.kill() if force else bg_process.process.terminate()
                del self.processes[bg_process.handle]
                return True

            return False
    def get_process(self,handle_or_pid:str) -> Optional[BackgroundProcess]:
        """
        Retrieves a background process by its handle or PID.
        """
        with self._lock:
            bg_process = self.processes.get(handle_or_pid)
            if bg_process is None:
                for proc in self.processes.values():
                    if str(proc.process.pid) == str(handle_or_pid):
                        return proc
            return bg_process
    def list_processes(self) -> List[Dict[str, Any]]:
        """
        Lists all background processes with their status and logs.
        """
        with self._lock:
            return [
                {
                    "handle": proc.handle,
                    "pid": proc.process.pid,
                    "name": proc.name,
                    "status": proc.is_running,
                    "exit_code": proc.exit_code,
                    "logs": proc.get_logs(tail_lines=10)
                }
                for proc in self.processes.values()
            ]
    def cleanup_all(self):
        """
        Cleans up all background processes on exit.
        """
        with self._lock:
            for proc in list(self.processes.values()):
                if proc.is_running:
                    self.stop_process(proc.handle, force=True)
            self.processes.clear()

process_manager = ProcessManager()
atexit.register(process_manager.cleanup_all)