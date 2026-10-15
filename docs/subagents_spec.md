# Subagents Architecture & Execution Specification

## 1. Problem Statement & Motivation

In a standard single-agent loop, every user query or workflow command sends:
1. The entire multi-turn conversation history (`messages`).
2. The full primary `system_prompt.md` (Global Memory, Project Memory, Repo Map, Skills Registry).
3. All ~25 tool JSON schemas (`raven_tools`).
4. Requests to the primary flagship model (`RAVEN_MODEL`).

For **context-independent or self-contained tasks**—such as generating a standup report from git logs (`/report`), inspecting diffs and committing staged changes (`/commit`), or scouting across dozens of files to answer a targeted codebase question—this architecture wastes money, increases latency, and pollutes the primary conversation context with intermediate tool outputs.

### Core Objectives
- **Cost Optimization:** Route self-contained tasks to `RAVEN_SMALL_MODEL` (or a subagent-specific model) with a minimal system prompt and a strictly filtered subset of tools.
- **Zero Context Pollution:** Execute subagents in an isolated, ephemeral message history (`[system, user, ...tool_turns]`) without sending or bloating the main session's context window.
- **Dual Invocation Modes (OpenCode-Inspired):**
  1. **Direct Slash-Command Workers:** Commands like `/report`, `/commit`, and `/subagent <name> <task>` spin up an isolated subagent directly from the TUI.
  2. **Tool-Invoked Subagents (`delegate_to_subagent`):** The primary agent can autonomously delegate exploratory or isolated sub-tasks to a specialist subagent and receive only the distilled summary back.

---

## 2. Subagent Definition & Discovery (`agent/core/subagent_manager.py`)

Subagents are defined via a combination of **built-in presets** and **custom Markdown files with YAML frontmatter**.

### 2.1 Discovery Hierarchy & Scopes
1. **Built-in Presets:** Always available in memory (`explore`, `git_ops`, `reporter`, `general`).
2. **Global Custom Subagents:** `~/.raven/subagents/*.md`
3. **Project-Local Custom Subagents:** `<project_root>/subagents/*.md`

*Precedence:* `Project-Local > Global > Built-in Presets`. Users can override any built-in subagent (e.g., to customize `git_ops` commit rules or pin a specific model) by placing a `<name>.md` file in `~/.raven/subagents/` or `./subagents/`.

### 2.2 Subagent Schema & YAML Frontmatter
Each custom subagent `.md` file uses zero-dependency YAML frontmatter (reusing the parser pattern from `skills_manager.py`), where the Markdown body serves as the subagent's `system_prompt`:

```markdown
---
name: explore
description: Fast read-only codebase scout for finding files, searching patterns, and summarizing architecture.
model: ""
max_steps: 12
ephemeral: false
allowed_tools:
  - find_file
  - read_file
  - search_file_content
  - search_codebase
---
You are Raven's Codebase Exploration Subagent...
```

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `str` | Filename stem | Unique lowercase identifier (`[a-z0-9_-]`). |
| `description` | `str` | Required | Concise description shown to the primary agent and in `/subagent` autocomplete. |
| `model` | `str` | `""` (Auto) | Optional explicit model override. |
| `max_steps` | `int` | `12` | Hard cap on tool-calling turns for this subagent. |
| `ephemeral` | `bool` | `False` | When invoked directly via slash command: if `True`, nothing is saved to main `chat_session.messages`; if `False`, only the compact user command and final assistant summary are appended (omitting all intermediate tool calls). |
| `allowed_tools` | `list[str]` | `[]` | Whitelist of tool names from `TOOL_REGISTRY` that this subagent is permitted to call. |

### 2.3 Built-in Subagent Presets

1. **`explore` (Codebase Scout)**
   - **Purpose:** Fast, read-only file discovery, grep searching, and architectural lookup without polluting the main context with raw file dumps.
   - **Allowed Tools:** `find_file`, `read_file`, `search_file_content`, `search_codebase`
   - **Max Steps:** `12`
   - **Ephemeral (Direct Mode):** `False` (appends final answer to session)

2. **`git_ops` (Git & Commit Specialist)**
   - **Purpose:** Inspect git status, diff unstaged/staged changes, stage files when requested, and commit staged changes with a clean lowercase commit message. Powers `/commit` and natural-language git delegation.
   - **Allowed Tools:** `get_git_status`, `get_staged_git_changes`, `get_git_diff`, `get_git_log`, `git_add`, `commit_staged_git_changes`
   - **Max Steps:** `8`
   - **Ephemeral (Direct Mode):** `False` (appends final commit confirmation to session)

3. **`reporter` (Work & Activity Reporter)**
   - **Purpose:** Generates standup and work reports strictly from git commit history over a specified time window. Powers `/report`.
   - **Allowed Tools:** `get_git_log`, `get_current_timestamp`
   - **Max Steps:** `6`
   - **Ephemeral (Direct Mode):** `True` (renders in TUI and records cost, does not bloat session history)

4. **`general` (General Isolated Worker)**
   - **Purpose:** Executes self-contained multi-step tasks (research, file drafting, isolated fixes) delegated by the user or primary agent.
   - **Allowed Tools:** `find_file`, `read_file`, `search_file_content`, `search_codebase`, `create_file`, `patch_file`, `execute_command`, `web_search`, `extract_content_from_web_links`, `get_current_timestamp`
   - **Max Steps:** `15`
   - **Ephemeral (Direct Mode):** `False`

---

## 3. Model Resolution Hierarchy

When a subagent is instantiated, its target model is resolved deterministically:

```text
1. Subagent `model` field (if explicitly set in preset/frontmatter)
   ↓ (if empty/unset)
2. settings.RAVEN_SMALL_MODEL (configured cheap/fast model)
   ↓ (if empty/unset)
3. parent_model or settings.RAVEN_MODEL (active primary model fallback)
```

If an API call fails due to an invalid/unavailable `RAVEN_SMALL_MODEL` on the first turn, the runner automatically falls back to `settings.RAVEN_MODEL` so execution never breaks when switching providers.

---

## 4. Isolated Execution Engine (`agent/core/subagent_runner.py`)

### 4.1 Context & Tool Isolation
- **Fresh Message Array:** Starts with `[{"role": "system", "content": subagent.system_prompt}, {"role": "user", "content": task_prompt}]`.
- **Zero Main Context Leakage:** Does **not** include the parent conversation history, global/project memory blocks, or unrelated tool schemas.
- **Strict Tool Whitelisting:**
  - Filters `raven_tools` to only the schemas listed in `subagent.allowed_tools`.
  - **Recursion & Deadlock Guard:** `delegate_to_subagent` and `ask_user` are unconditionally stripped from subagent tool schemas so a subagent can never spawn nested subagents or block on a multi-question modal.

### 4.2 Bounded Loop Guard
- Each subagent run initializes its own lightweight `LoopGuard` configured with `max_turns = subagent.max_steps` and `hard_max_turns = subagent.max_steps + 2`.
- Duplicate tool calls with identical arguments are intercepted immediately.
- When `max_steps` is reached, the runner disables further tool calls (`allow_tools=False`) and forces a final synthesis turn so the subagent always returns a coherent summary.

### 4.3 Permission Gating & Cancellation
- **Cancellation:** Respects the active `cancel_event` (`Ctrl+C` / `Escape` in TUI), immediately aborting the subagent's active HTTP stream and breaking its loop.
- **Gated Tools:** If a subagent attempts to invoke `execute_command`, `start_background_process`, or `commit_staged_git_changes`:
  - Checks `settings.RAVEN_AUTO_APPROVE` and `is_command_dangerous()` identically to the main agent.
  - If manual approval is required, invokes the injected `permission_callback(tool_name, tool_args)` which bridges to the TUI's `ask_permission_ui` bar.

### 4.4 Token & Cost Accounting
- Every streaming/non-streaming LLM turn inside `SubAgentRunner` captures `prompt_tokens`, `completion_tokens`, `duration_ms`, and `ttft_ms`.
- If bound to the active `chat_session.tracker` (or global `UsageTracker`), it records each turn under the **subagent's actual `model_name`** so token analytics (`/usage`) and session cost totals remain 100% accurate.

---

## 5. Dual Invocation Modes

### Mode A: Direct Slash-Command Execution (TUI)
1. **`/report [time_period]`**
   - Routed directly to the **`reporter`** subagent (`ephemeral=True`).
   - Does not send main chat history; runs on `RAVEN_SMALL_MODEL` with only `get_git_log` and `get_current_timestamp`.
2. **`/commit [optional instructions]`**
   - New slash command! Routed directly to the **`git_ops`** subagent.
   - Inspects staged changes (`get_staged_git_changes`), or checks `get_git_status` if nothing is staged, generates a concise lowercase commit message, and calls `commit_staged_git_changes`.
3. **`/subagent <name> <task_prompt>`** (and `/subagents` to list available subagents)
   - Allows the user to directly invoke any built-in or custom subagent in an isolated context while streaming its tool timeline and output directly into a TUI `ChatMessageWidget`.
   - The `ChatMessageWidget` header displays the subagent badge and model used (e.g., `Raven [subagent: git_ops • gemini-2.5-flash-lite]`).

### Mode B: Autonomous Tool Delegation (`delegate_to_subagent`)
- Exposed as a native tool in `raven_tools` for the primary agent:
  ```json
  {
    "name": "delegate_to_subagent",
    "description": "Delegate a self-contained or context-independent task to a specialized isolated subagent (runs on a fast/cheap model with its own isolated context and filtered tools).",
    "parameters": {
      "subagent_name": {
        "type": "string",
        "description": "Name of the subagent to invoke ('explore', 'git_ops', 'reporter', 'general', or a custom subagent)."
      },
      "task_prompt": {
        "type": "string",
        "description": "Clear, self-contained instructions and context for the subagent to complete."
      }
    }
  }
  ```
- During execution inside `stream_response`:
  - The main timeline shows `Subagent: <subagent_name>` as a running tool call.
  - The thinking loader updates dynamically as the subagent executes its internal steps (`Subagent [explore]: Executing Read File...`).
  - Returns a structured string containing the subagent's final output, steps taken, and model used, keeping all intermediate file reads/grep outputs out of the primary model's context window.
