from dataclasses import dataclass
import subprocess
import time
import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional

@dataclass
class BackgroundProcess:
    handle:str
    process: subprocess.Popen
    name:str = ""

    def __post_init__(self) -> None:
        if self.name: self.name = self.handle
        self.start_time = time.time()
        self.log_buffer = deque(maxlen=200)  # Store the last 200 log lines
        self._lock = threading.Lock()
        self._start_log_reader()

    def _start_log_reader(self):
        def _read_stream(stream):
            for line in iter(stream.readline,''):
                with self._lock:
                    self.log_buffer.append(line.rstrip("\r\n"))
            stream.close()
        threading.Thread(target=_read_stream,args=(self.process.stdout,),daemon=True).start()
        threading.Thread(target=_read_stream,args=(self.process.stderr,),daemon=True).start()
    
    def get_logs(self,tail_lines:int=10) -> List[str]:
        with self._lock:
            lines = list(self.log_buffer)[-tail_lines:]
        return "\n".join(lines)
    @property
    def is_running(self) -> bool:
        return self.process.poll(0) is None
    @property
    def exit_code(self) -> Optional[int]:
        return self.process.poll()

@dataclass
class ProcessManager:

