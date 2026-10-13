# Specification: Instant Agent Loop Cancellation on Escape Key Interrupt

## 1. Overview & Goal

Currently, pressing the `Escape` key does not halt the agent execution loop instantly. Delays occur because:
1. Synchronous tool executions (e.g., `execute_command`, shell operations, file I/O, or web searches) block the worker thread, delaying the evaluation of `cancel_event.is_set()`.
2. Intermittent socket reads during LLM streaming block until the next chunk arrives or times out.
3. UI modals (permission requests and questionnaire bars) intercept `Escape` to reject options or dismiss UI components without invoking `cancel_event.set()`.

This specification details the architecture required for **sub-100ms instant cancellation** of the agent generation loop, running processes, network streams, and modal states upon pressing `Escape`.

---

## 2. Architectural Design

```
                     [ User Presses ESCAPE ]
                               |
                               v
                +------------------------------+
                | action_cancel_generation()   |
                +------------------------------+
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
[ Set cancel_event ]   [ Dismiss Modals ]     [ Abort Active Process ]
       |                       |                       |
       v                       v                       v
Unblock Loop Waiters   Clear Permission /      Kill Child Subprocess Tree
                       Questionnaire State     (taskkill / PID terminate)
```

---

## 3. Core Technical Changes

### 3.1 Unconditional Global Cancellation in UI Handler (`agent/terminal_ui/app.py`)

* **Current Defect:** `action_cancel_generation()` checks `if self.pending_permission:` or `if self.pending_questionnaire:` and returns early after resolving modal promises, leaving `self.cancel_event` unset.
* **Specification Fix:** `action_cancel_generation()` MUST unconditionally trigger `self.cancel_event.set()` and `self.questionnaire_event.set()`, ensuring both UI components and background generation workers stop simultaneously.

```python
def action_cancel_generation(self):
    """Interrupts active AI generation, closes active modals, and kills active tool processes instantly."""
    # 1. Trigger global cancellation signal first
    self.cancel_event.set()
    self.questionnaire_event.set()

    # 2. Resolve pending UI modals if present
    if self.pending_permission:
        self.resolve_permission(granted=False, instruction="User cancelled generation via Escape key.")

    if self.pending_questionnaire:
        self.on_questionnaire_completed({"status": "cancelled", "answers": {}})

    # 3. Abort active child process tree if executing synchronous shell command
    self.kill_active_executing_process()

    # 4. Hide autocomplete overlay if open
    autocomplete = self.query_one("#autocomplete_list", OptionList)
    if autocomplete.styles.display == "block":
        autocomplete.styles.display = "none"
        self.query_one("#chat_input", ChatInput).styles.margin = (0, 0, 0, 0)
```

---

### 3.2 Active Subprocess Tracking & Forceful Interruption (`agent/core/process_manager.py` / `agent/tools/process_tools.py`)

* **Current Defect:** Synchronous tools (e.g. `execute_command`) call `subprocess.run()` or `popen.communicate()` in blocking mode. The thread cannot check `cancel_event` until execution finishes.
* **Specification Fix:**
  1. Introduce an `active_process_registry` tracking current running sync subprocess PIDs in thread-local or manager state.
  2. Implement `kill_active_executing_process()` inside process management tools.
  3. When `cancel_event` is set, `kill_active_executing_process()` immediately issues a process tree kill command:
     * **Windows:** `taskkill /F /T /PID <pid>`
     * **POSIX:** `os.killpg(os.getpgid(pid), signal.SIGKILL)`

```python
# Active process tracking interface
active_sync_process: subprocess.Popen | None = None
process_lock = threading.Lock()

def set_active_sync_process(proc: subprocess.Popen | None):
    global active_sync_process
    with process_lock:
        active_sync_process = proc

def kill_active_sync_process():
    global active_sync_process
    with process_lock:
        if active_sync_process is not None and active_sync_process.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(active_sync_process.pid)], capture_output=True)
                else:
                    os.killpg(os.getpgid(active_sync_process.pid), signal.SIGKILL)
            except Exception:
                pass
            active_sync_process = None
```

---

### 3.3 HTTP Transport Socket & Streaming Interruption (`agent/core/llm.py`)

* **Current Defect:** The LLM client loop iterates over response chunks (`for chunk in response:`). If the provider API network connection stalls or buffers slowly, cancellation stays pending until the next chunk arrives.
* **Specification Fix:**
  1. Pass the underlying `httpx.Response` object or stream handle to a cancellable context manager.
  2. Upon `cancel_event.set()`, explicitly call `response.close()` on the HTTP stream to force an immediate socket disconnection and break out of chunk iteration loops instantly with `stream.close()`.

---

### 3.4 Verification & Error Handling Criteria

1. **Sub-100ms Interruption:** Pressing `Escape` at any point during output generation, permission prompt display, or long shell command execution MUST stop visual spinner animations and update the chat timeline to `Generation stopped by user` within 100ms.
2. **Resource Clean-up:** Orphaned child shell processes MUST NOT remain running in the OS process table after cancellation.
3. **Re-usability:** The chat input area MUST immediately accept new prompt entries right after cancellation without requiring CLI restart.

---

## 4. Implementation Steps

1. Patch `agent/terminal_ui/app.py`: update `action_cancel_generation()` for unconditional cancellation and process termination dispatch.
2. Update `agent/tools/miscellaneous_tools.py` and `agent/core/process_manager.py`: register active PIDs during execution and implement `kill_active_sync_process()`.
3. Update `agent/core/llm.py`: add HTTP stream socket closing capability when `cancel_event` triggers.
