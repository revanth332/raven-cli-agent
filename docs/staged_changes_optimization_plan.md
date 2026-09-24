# Staged Changes Tool Optimization Plan

## Objective
Optimize `get_staged_git_changes` and streamline git diff inspection by eliminating subprocess redundancy, fixing exception handling, adding context-protection truncation/noise filtering, and correcting display metadata.

---

## Plan & Tasks

### 1. Single Subprocess Execution & Error Handling
- Remove the redundant `git diff --cached --quiet` pre-check.
- Execute `git diff --cached` once with `errors="replace"` and check `result.returncode`.
- Return `stderr` directly when returncode != 0 (e.g., repository not initialized).
- Use `try...except Exception as e` to catch process invocation failures.

### 2. Output Clamping & Noise Exclusion
- Add safety limits to prevent LLM context flooding on large commits:
  - Capped at `max_lines` (default: 500 lines / ~25KB).
  - Exclude noisy files by default or summarize diff headers when exceeding limit.
  - Return clear truncation notification if lines exceed `max_lines`.

### 3. Display Metadata Alignment
- In `agent/tools/tool_registry.py`, update `get_staged_git_changes` display name from `"Search changes"` to `"Staged Changes"`.

---
