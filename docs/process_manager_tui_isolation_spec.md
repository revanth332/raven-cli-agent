# Specification: Process Manager & Subprocess TUI Isolation (Win32 & Terminal Safety)

## 1. Overview & Objectives

When Raven executes terminal commands (`execute_command`) or manages long-running services (`start_background_process`, `check_process_status`), subprocesses run alongside the active Textual Terminal User Interface (TUI). 

On Windows, child processes share the active Console Screen Buffer (`conhost.exe` / Windows Terminal) by default unless explicitly isolated. This leads to severe visual glitches—such as raw host progress banners overriding the TUI viewport (e.g. PowerShell `Invoke-WebRequest` progress bars), corrupted ANSI escape sequences (`30;30m`), TUI freezing from blocking child stdin/stdout streams, and GIL starvation from high-frequency log spam.

### Primary Objectives:
- **Zero Console Screen Bleed:** Completely isolate child processes from the parent console screen buffer using Win32 creation flags (`CREATE_NO_WINDOW`).
- **PowerShell Host UI Suppression:** Enforce non-interactive execution flags and silence `$ProgressPreference` to prevent PowerShell from hijacking the screen.
- **Hang & Timeout Immunity:** Prevent infinite hangs in synchronous `execute_command` by adding configurable default execution timeouts.
- **Stream & Encoding Resilience:** Eliminate `UnicodeDecodeError` crashes in stream reader threads and properly handle carriage-return (`\r`) progress lines.
- **Markup & ANSI Sanitization:** Ensure no unescaped Rich markup or orphan terminal escape codes are rendered in the TUI chat message stream.
- **Clean Process Tree Termination:** Ensure child and grandchild processes (e.g., `cmd` -> `node` -> `vite`) are reliably killed without leaving orphaned background services.

---

## 2. Root Cause Analysis & Edge Cases

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PARENT PROCESS (Textual TUI)                    │
│   Active Conhost / VT100 Screen Buffer (Render Loop: 60 FPS)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ❌ WITHOUT ISOLATION            │   ✅ WITH CREATE_NO_WINDOW
    ┌───────────────────────────┐   │   ┌───────────────────────────────┐
    │ Subprocess inherits       │   │   │ Subprocess detached from con- │
    │ parent Console Buffer:    │   │   │ sole buffer. Writes piped to  │
    │ • Write-Progress bars     │   │   │ in-memory log buffer safely.  │
    │ • Raw ANSI color codes    │   │   └───────────────────────────────┘
    │ • Mid-stream redraw clash │   │
    └───────────────────────────┘   │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    CHILD SUBPROCESS (PowerShell / Node)                │
└────────────────────────────────────────────────────────────────────────┘
```

### Edge Case 1: Shared Console Screen Buffer Leakage (Win32 Conhost Bleed)
* **Root Cause:** When `subprocess.Popen` or `subprocess.run` is called on Windows with `shell=True` and only `CREATE_NEW_PROCESS_GROUP` (or no flags), the process remains attached to the parent console buffer. Low-level Win32 console API calls (such as `WriteConsoleOutput` or conhost character grid draws) write directly to the physical terminal grid, completely bypassing Textual's virtual DOM rendering.
* **Manifestation:** Bright cyan banners (`Writing web request... (Number of bytes written: ...)`), flickering text, corrupted viewports.

### Edge Case 2: PowerShell Direct Host UI & Write-Progress Hijack
* **Root Cause:** PowerShell's `Invoke-WebRequest`, `Invoke-RestMethod`, and package installation cmdlets output graphical text progress bars by default via the host's `Write-Progress` system.
* **Manifestation:** Even with redirected `stdout` and `stderr`, PowerShell host UI events are rendered straight to the top rows of the active console session.

### Edge Case 3: Infinite Hangs in Synchronous `execute_command`
* **Root Cause:** `subprocess.run` inside `agent/tools/miscellaneous_tools.py` has no `timeout` parameter. If a command prompts for interactive input (`[y/N]`, `Press any key to continue...`, `git commit` without `-m`, or a long-running daemon accidentally executed as a standard command), the agent freezes indefinitely (e.g., 1900+ seconds thinking spinner).

### Edge Case 4: ANSI & Control Sequence Fragmentation
* **Root Cause:** Terminal utilities output carriage returns (`\r`), ANSI cursor positioning (`\x1b[1A`, `\x1b[2K`), and 24-bit RGB sequences (`\x1b[38;2;...m`). If an escape sequence is chunked or malformed, raw tokens (e.g., `;30;30m`) leak into the chat interface as visible text.

### Edge Case 5: `UnicodeDecodeError` in Background Stream Threads
* **Root Cause:** In `BackgroundProcess._start_log_reader()`, opening streams with `text=True` defaults to the system locale (often `cp1252` or `cp437` on Windows). When a child process outputs UTF-8 symbols, emojis, or binary bytes (e.g., curl downloading binary to stdout), the reader thread crashes with `UnicodeDecodeError` and stops streaming logs entirely.

### Edge Case 6: Carriage-Return (`\r`) Progress Flooding & Readline Block
* **Root Cause:** Tools like `npm`, `pip`, and `curl` write download progress using `\r` instead of `\n`. Python's `stream.readline()` waits for a newline (`\n`), buffering thousands of progress updates until the command completes or stalling in the worker thread.

### Edge Case 7: High-Frequency Output Flooding (GIL Contention)
* **Root Cause:** Tight loops (e.g. `while(1) console.log(...)`) spitting 50,000 lines/sec overwhelm the Python thread lock (`self._lock.acquire()`), consuming 100% CPU and starving Textual's UI event loop.

### Edge Case 8: Orphaned Grandchild Processes on Windows
* **Root Cause:** Calling `proc.terminate()` or `proc.kill()` on Windows terminates only the parent shell (`cmd.exe` or `powershell.exe`), leaving the actual running runtime (e.g. `node.exe`, `python.exe`, `esbuild`) orphaned in the background holding ports.

---

## 3. Architecture & Remediation Design

### 3.1 Subprocess Creation Flags (Windows Isolation)
On Windows (`os.name == 'nt'`), every subprocess invocation across both `ProcessManager` and `execute_command` MUST combine:
1. `subprocess.CREATE_NO_WINDOW` (`0x08000000`): Completely detaches the child from the console buffer and prevents new console window popups.
2. `subprocess.CREATE_NEW_PROCESS_GROUP` (`0x00000200`): Allows independent signal handling so CTRL+C in Raven does not abruptly kill background daemons unless intended.

```python
# creationflags construction
creationflags = 0
if os.name == 'nt':
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
```

### 3.2 Automated PowerShell Command Wrapping
Whenever a command invokes `powershell` or `pwsh`, or is executed in a PowerShell context:
- Automatically inject `-NoProfile -NonInteractive -ExecutionPolicy Bypass`.
- Prepend `$ProgressPreference = 'SilentlyContinue';` to disable the `Write-Progress` host engine.

```python
def sanitize_command(command: str) -> str:
    lower_cmd = command.strip().lower()
    if lower_cmd.startswith("powershell") or lower_cmd.startswith("pwsh"):
        # Ensure progress is silent and interactive prompts disabled
        if "$progresspreference" not in lower_cmd:
            # Wrap script block safely with SilentlyContinue
            return command
    return command
```

### 3.3 Synchronous Timeout & Output Capping in `execute_command`
- Set a strict default timeout (e.g. `120` seconds) on `execute_command`.
- Catch `subprocess.TimeoutExpired`, safely terminate the process tree using `taskkill /PID {pid} /T /F`, and return a clear timeout error message advising the LLM to use `start_background_process` for long-running jobs.

### 3.4 Robust Binary Stream Decoding with `\r` Normalization
- Open process streams in binary mode (`stdout=subprocess.PIPE`, `stderr=subprocess.PIPE`).
- Decode using `errors='replace'` and UTF-8 encoding.
- Process chunks splitting by both `\r\n`, `\n`, and `\r` to capture active progress steps without buffering gigabytes.

```python
def _read_stream(stream):
    try:
        buffer = ""
        while True:
            chunk = stream.read(1024)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            buffer += text
            while "\n" in buffer or "\r" in buffer:
                # Process lines or carriage returns
                ...
    except Exception:
        pass
    finally:
        stream.close()
```

### 3.5 Textual / Rich Markup Sanitization in Chat Outputs
- Any output rendered from `execute_command` or `check_process_status` displayed in UI widgets (`chat_message.py`) must pass through `rich.markup.escape()` or `strip_ansi()` to ensure stray brackets (e.g. `[1/5]`, `[error]`) or corrupted escape codes do not corrupt the terminal screen.

### 3.6 Resilient Process Tree Cleanup (`taskkill /T /F`)
- On Windows, `stop_process` and `cleanup_all` must reliably issue `taskkill /PID {pid} /T /F` with `CREATE_NO_WINDOW` so `taskkill` itself does not pop console flashes.

---

## 4. Implementation Checklist

- [ ] **`agent/core/process_manager.py`**:
  - Update `start_process` to use `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`.
  - Fix stream reader thread to use binary decoding with `errors="replace"`.
  - Add rate-limiting / chunk throttling to log buffer under heavy spam.
  - Ensure `stop_process` uses `CREATE_NO_WINDOW` for `taskkill`.
- [ ] **`agent/tools/miscellaneous_tools.py`**:
  - Add `timeout=120` to `subprocess.run` inside `execute_command`.
  - Add `CREATE_NO_WINDOW` to `creationflags` in `execute_command`.
  - Enhance `strip_ansi` regex to purge broken/orphan ANSI artifacts.
- [ ] **`agent/terminal_ui/chat_message.py`**:
  - Ensure raw tool outputs passed to Textual widgets are properly sanitized and markup-escaped.
- [ ] **`agent/prompts/system_prompt.md`**:
  - Remind the agent model to use `$ProgressPreference = 'SilentlyContinue'` and `start_background_process` for any downloads, servers, or builds.

---

## 5. Verification & Acceptance Criteria
1. **PowerShell Download Test:** Running `powershell -Command "Invoke-WebRequest ..."` or large downloads does not paint any cyan bars or text outside the chat container.
2. **Interactive Prompt Test:** Running a blocking command (e.g. `pause` or input wait) times out gracefully after 120s without hanging Raven.
3. **ANSI & Emojis Test:** Processes emitting emojis, complex color codes, or `\r` progress bars render cleanly without orphan codes (like `;30;30m`) or `UnicodeDecodeError` crashes.
4. **Clean Exit:** Starting a server with `start_background_process` and exiting Raven terminates the full process tree cleanly with zero orphaned node/python instances.
