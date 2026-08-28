# Sprint Board & Story Backlog — EPIC MEM-01

**Active Sprint:** Sprint 1 — Memory Engine Architecture  
**Status Key:** ⚪ Todo | 🟡 In Progress | 🟠 Code Review | 🟢 Done

---

## 📋 Active Tickets

### [🟢 DONE] MEM-101: Prompt Directives Refactor & Legacy Memory Schema Migration

- **Assignee:** @Revathipathi
- **Estimate:** 2 SP
- **Description:** Remove git commit log mandates from the system prompt, repurpose `save_to_project_memory` for architectural state only, and migrate active project memory from raw logs to the structured 3-section format.
- **Acceptance Criteria (AC):**
  - [x] `agent/prompts/system_prompt.md`: Strip out mandatory commit logging instructions.
  - [x] `agent/prompts/system_prompt.md`: Update instructions for `save_to_project_memory` to focus solely on high-value architecture, tech stack, and hard constraints.
  - [x] `~/.raven/memory/projects/{project}.md`: Refactored to structured layout with clean sections.
  - [x] Zero prompt generation errors in `get_chat_session()`.
- **Definition of Done (DoD):**
  - [x] Prompt file updated and verified.
  - [x] Project memory file cleaned of historical commit logs.
  - [x] Lead architect code review approval.

---

### [🟢 DONE] MEM-102: Tool Registry Cleanup & Direct Patching Memory Integration

- **Assignee:** @Revathipathi
- **Estimate:** 2 SP
- **Description:** Complete deprecation and removal of `save_to_project_memory` across the tool registry, core LLM setups, and memory tools, fully delegating project memory edits to `patch_file`.
- **Acceptance Criteria (AC):**
  - [x] Remove `save_to_project_memory` declaration from `agent/tools/tool_registry.py` (both `raven_tools` and `TOOL_REGISTRY`).
  - [x] Remove `save_to_project_memory` function from `agent/tools/memory_tools.py`.
  - [x] Ensure all references across `agent/core/llm.py` and test suites are cleaned up.
  - [x] Verify `get_active_projects` is properly registered or retained for project memory navigation.
- **Definition of Done (DoD):**
  - [x] Tool registry cleaned up without orphan functions.
  - [x] Existing test suite passes with zero errors.
  - [x] Lead architect code review approval.

---

### [🟡 IN PROGRESS] MEM-103: Automated Memory Compactor & Distillation Routine

- **Assignee:** @Revathipathi
- **Estimate:** 5 SP
- **Description:** Implement an automated compaction mechanism that triggers when a project memory file exceeds token or entry thresholds, distilling and consolidating the active project state.
- **Acceptance Criteria (AC):**
  - [ ] Implement a compaction evaluation utility (`should_compact_memory(content: str)` or token count threshold, e.g. > 1,200 tokens).
  - [ ] Implement `compact_project_memory(project_name: str)` that runs a distillation pass to clean up bloated sections, remove stale tasks, and synthesize redundant bullets into a concise state.
  - [ ] Safe atomic file overwrite (write to temp/validated content before replacing existing memory).
  - [ ] Graceful fallback if the distillation call fails (never destroy memory on API timeout/error).
- **Definition of Done (DoD):**
  - Compaction function implemented with error handling.
  - Unit tests covering token threshold checking and distillation fallback.

---

### [⚪ TODO] MEM-103: Automated Memory Compactor & Distillation Routine

- **Assignee:** Unassigned
- **Estimate:** 5 SP
- **Description:** Implement an LLM-based state consolidation engine that compresses and distills project memory when it exceeds token or entry thresholds.
- **Acceptance Criteria (AC):**
  - [ ] Token count / entry length threshold check before/after memory mutation.
  - [ ] Distillation prompt synthesized to merge points and drop obsolete decisions.
  - [ ] Atomic file write to avoid corrupted memory files on compaction failure.
- **Definition of Done (DoD):**
  - Compaction trigger tested under high-load synthetic memory inputs.
  - Graceful fallback if compaction LLM call fails.

---

### [⚪ TODO] MEM-104: Semantic Episodic Memory Tool (`recall_memory` via ChromaDB)

- **Assignee:** Unassigned
- **Estimate:** 3 SP
- **Description:** Connect debugging logs (`debug_history.md`) and concepts to a dedicated ChromaDB collection for dynamic semantic querying.
- **Acceptance Criteria (AC):**
  - [ ] Create `raven_episodic_memory` collection in ChromaDB.
  - [ ] Implement `recall_memory(query: str)` tool.
  - [ ] Register `recall_memory` in `agent/tools/tool_registry.py`.
- **Definition of Done (DoD):**
  - Semantic queries accurately fetch historical debug fixes.
  - System prompt stays lean without raw debug history.

---

### [⚪ TODO] MEM-105: Unit Tests, Integration Benchmarks & Documentation

- **Assignee:** Unassigned
- **Estimate:** 2 SP
- **Description:** Comprehensive test coverage for memory persistence, compaction, and semantic retrieval.
- **Acceptance Criteria (AC):**
  - [ ] Unit tests in `tests/test_memory_tools.py`.
  - [ ] Integration test validating full cycle: state update → threshold compaction → recall.
  - [ ] Update `architecture.md` and project brief.
- **Definition of Done (DoD):**
  - 100% test pass rate across the test suite.
  - Final PR merge sign-off.
