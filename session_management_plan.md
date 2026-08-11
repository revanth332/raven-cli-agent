# Session Management Implementation Plan

## Overview & Scope

The session management feature establishes a JSON-backed persistence layer in `~/.raven/sessions/` that serializes conversation histories, active models, and metadata per unique session ID. It integrates with `AgentChatSession` and Textual TUI via `/new`, `/sessions`, and `/switch` slash commands to enable seamless conversation state creation, listing, switching, and UI header updates.

## Phase 1: Core Session Persistence Subsystem

### Step 1.1: Define Session Data Schema & Storage Directory

- **Files Impacted**: `agent/core/session_manager.py`
- **Objective**: Establish the core data schema for sessions (containing `session_id`, `title`, `created_at`, `updated_at`, `model_name`, and `messages` array) and ensure automatic initialization of the storage directory at `~/.raven/sessions/`.
- **Dependencies**: None.
- **Verification**: Run `python -c "from agent.core.session_manager import get_sessions_dir; print(get_sessions_dir())"` and verify the directory is created on disk.

### Step 1.2: Implement Session Persistence CRUD Engine

- **Files Impacted**: `agent/core/session_manager.py`
- **Objective**: Implement core CRUD functions (`create_session`, `save_session`, `load_session`, `list_sessions`, `delete_session`) that handle file read/write operations with atomic file writes and error handling for corrupt files.
- **Dependencies**: Step 1.1
- **Verification**: Run a manual Python script creating a mock session, saving it to disk, reading it back, and verifying payload equivalence.

### Step 1.3: Integrate Serialization into AgentChatSession

- **Files Impacted**: `agent/core/llm.py`
- **Objective**: Extend `AgentChatSession` to accept a `session_id`, auto-save message turns on every assistant response, auto-generate conversation titles from initial prompt summaries, and restore full context arrays upon loading.
- **Dependencies**: Step 1.2
- **Verification**: Instantiate `AgentChatSession`, send a message stream turn, and confirm a corresponding `.json` session file is written/updated in `~/.raven/sessions/`.

---

## Phase 2: CLI Slash Commands & TUI UI Integration

### Step 2.1: Create Session Selection Modal Component

- **Files Impacted**: `agent/terminal_ui/session_select_modal.py`
- **Objective**: Create a Textual `ModalScreen` component (`SessionSelectModal`) that displays a searchable option list of all existing sessions formatted with title, turn count, last active timestamp, and model name.
- **Dependencies**: Step 1.2
- **Verification**: Mount the modal in a standalone test script and verify that keyboard arrows, selection events, and escape/dismiss keys function properly.

### Step 2.2: Register `/new`, `/sessions`, and `/switch` Slash Commands in Terminal UI

- **Files Impacted**: `agent/terminal_ui/app.py`, `agent/terminal_ui/chat_input.py`
- **Objective**: Add `/new` (start fresh conversation), `/sessions` or `/switch` (open `SessionSelectModal`) slash commands to autocomplete list and handle execution events in `app.py`.
- **Dependencies**: Step 2.1, Step 1.3
- **Verification**: Type `/new` in the terminal UI and verify chat messages reset; type `/sessions` and verify the selection modal opens.

### Step 2.3: Update TUI Message Display & Active Session Header Indicator

- **Files Impacted**: `agent/terminal_ui/app.py`
- **Objective**: Update the TUI status bar and welcome screen to display the active session title/ID and re-render existing history cards on the chat screen when switching sessions.
- **Dependencies**: Step 2.2
- **Verification**: Switch between two different sessions in the UI and verify that all past chat cards update dynamically to match the selected conversation history.

---

## Phase 3: Testing & Verification

### Step 3.1: Unit Tests for Session Persistence & File Integrity

- **Files Impacted**: `tests/test_session_manager.py`
- **Objective**: Create unit tests covering session creation, message appending, updating metadata, listing sorted by `updated_at`, handling missing files, and handling malformed JSON safely.
- **Dependencies**: Step 1.3
- **Verification**: Execute `python -m unittest tests/test_session_manager.py` and confirm all unit test assertions pass with 100% success.

### Step 3.2: Async Pilot Tests for TUI Session Switching

- **Files Impacted**: `tests/test_ui_sessions.py`
- **Objective**: Write Textual async `run_test` pilot tests that simulate submitting messages, invoking `/new`, selecting a past session via `SessionSelectModal`, and validating DOM card counts.
- **Dependencies**: Step 2.3, Step 3.1
- **Verification**: Run `python -m unittest tests/test_ui_sessions.py` and ensure zero failures or UI freeze regressions.

---

## Cross-Cutting Concerns

- **Security/Auth**: Session files must be stored with strict OS-level permissions (`0700` directory / `0600` files) under the user's local profile (`~/.raven/sessions/`) to prevent unauthorized access to sensitive conversation data or tool logs.
- **Performance**: Large conversation files should lazily load message contents; `list_sessions()` will only parse metadata headers (first 1KB or top-level keys) to keep autocomplete and modal rendering instantaneous regardless of history size.
- **Rollback Plan**: If a session file fails to load or experiences JSON parsing corruption, the agent safely falls back to creating a new default session in memory with a user warning notification, preserving all existing session files intact.
