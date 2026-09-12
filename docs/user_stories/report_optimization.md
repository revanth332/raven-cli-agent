# User Stories: /report Command & Context Optimization

## Epic Overview
The `/report` command and tool execution pipeline currently risk blowing up LLM context windows due to dumping raw git patch diffs (`git log -p`), lacking output truncation in `execute_command`, employing repetitive manual 5-commit stepping, and prompting the user unnecessarily for author and time period info. 

The goal of this epic is to eliminate context bloat, reduce token consumption and latency, and make `/report` fast, robust, and autonomous.

---

## Story 1: Smart Defaults & Prompt Optimization for `/report`
**ID:** `US-REPORT-001`  
**Priority:** High  
**Status:** Completed  

### Description
As a user running `/report`, I want the agent to automatically infer sensible defaults (e.g., current author via git config, past 7 days if unspecified) and fetch compact summaries (`--stat`) instead of entire patch diffs (`-p`), so that context isn't blown up by thousands of lines of code changes.

### Acceptance Criteria
1. **Remove `-p` Diff Dumps:** Update `agent/prompts/report_prompt.md` to forbid raw patch diffs (`-p`) by default. Replace with `--stat` or `--name-status` to inspect changed files and change magnitude (+/-).
2. **Path Filter Exclusions:** Add instructions/flags to ignore lockfiles, binaries, and generated files (e.g., `:(exclude)*lock*`, `:(exclude)*.min.*`).
3. **Smart Time Period Default:** In `agent/terminal_ui/app.py`, if the user enters `/report` without arguments, default `<time_period>` to `"past 7 days"` instead of empty string.
4. **Author Auto-Detection:** Instruct the agent to detect the author name automatically (e.g., via `git config user.name` or latest local commit) instead of pausing to ask the user.
5. **Eliminate 5-Commit Step Loop:** Allow git's native `--since` / `--until` flags to retrieve all relevant commits in a single round-trip instead of iterative 5-commit queries.

---

## Story 2: Output Capping & Truncation Guard for `execute_command`
**ID:** `US-REPORT-002`  
**Priority:** High  
**Status:** Completed  

### Description
As an agent runtime, I want shell command execution (`execute_command`) to enforce maximum character and line limits on stdout/stderr, so that any command generating massive output cannot exhaust model token context or trigger 429 quota errors.

### Acceptance Criteria
1. **Output Limit Guard:** In `agent/tools/miscellaneous_tools.py`, cap stdout and stderr to a safe limit (e.g., max 6,000 characters or ~120 lines).
2. **Informative Truncation Notice:** If output exceeds the threshold, truncate the middle or tail and append a clear banner:
   `"... [Output truncated: X lines / Y characters omitted. Please filter your command query]"`
3. **Return Exit Codes:** Ensure exit codes and initial error traces remain visible when truncated.
4. **Unit Tests:** Add comprehensive unit tests in `tests/test_command_truncation.py` covering within-limit and exceeding-limit outputs.

---

## Story 3: Dedicated Git Log Tool (`get_git_log`)
**ID:** `US-REPORT-003`  
**Priority:** Medium  
**Status:** Completed  

### Description
As a developer agent, I want a dedicated, structured `get_git_log` tool in `agent/tools/git_tools.py` rather than relying on unstructured shell execution, so that git history retrieval is predictable, fast, safely capped, and cross-platform.

### Acceptance Criteria
1. **Tool Definition:** Implement `get_git_log(author: str = None, since: str = "7 days ago", until: str = None, max_commits: int = 20, include_stat: bool = True)` in `agent/tools/git_tools.py`.
2. **Automatic Sanitization:** Automatically exclude noisy paths (e.g. `package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `dist/*`, `build/*`).
3. **Registry & Schema Integration:** Register in `agent/tools/tool_registry.py` and add OpenAI function tool schema in `agent/core/llm.py`.
4. **Prompt Update:** Update `agent/prompts/report_prompt.md` to utilize `get_git_log` tool instead of ad-hoc `execute_command` strings.
5. **Unit Tests:** Add unit tests verifying parameter handling, output structure, and error scenarios.

---

## Story 4: End-to-End Verification & Documentation
**ID:** `US-REPORT-004`  
**Priority:** Medium  
**Status:** Completed  

### Description
As a developer, I want regression tests and validation for the `/report` command across repos with large commit histories to ensure fast response times and compact context footprints.

### Acceptance Criteria
1. **Execution Verification:** Test `/report` and `/report 2 weeks` commands to verify prompt rendering and tool calling.
2. **Context Token Verification:** Verify that token consumption for report generation is reduced significantly compared to unconstrained diff dumping.
3. **Documentation:** Update `architecture.md` if any new tool is introduced, and update active project memory.
