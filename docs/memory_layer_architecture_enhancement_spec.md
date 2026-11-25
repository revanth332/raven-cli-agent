# Memory Layer Architecture Enhancement Specification

## 1. Executive Summary

This specification outlines the evolution of Raven's memory subsystem from a naive append-only store to an intelligent, conflict-resolving, recency-weighted, and KV-cache-safe memory architecture. 

The core objectives are:
1. **Eliminate Contradictions & Redundancy:** Transition global memory from append-only to state-reconciling CRUD (Create, Read, Update, Delete) with conflict detection.
2. **Optimize Context Retrieval Efficiency:** Stop polluting episodic BM25 (Best Matching 25) recall with globally injected rules; index cross-project memories instead.
3. **Automate Episodic Activation:** Introduce an automated pre-emptive recall hook triggered on runtime and command execution failures.
4. **Recency & Utility Decay Scoring:** Upgrade ranking from pure BM25 term frequency to a hybrid scoring model incorporating time decay and proven hit counts.
5. **Preserve KV (Key-Value) Cache Invariance:** Stop in-place mutation of `messages[0]` mid-session, protecting TTFT (Time-To-First-Token) and eliminating API (Application Programming Interface) cache-miss penalties.

---

## 2. Architecture & Tier Review

Raven's memory layer operates across 5 canonical tiers:

```
+-------------------------------------------------------------------------+
| Tier 1: Static Rules & Preferences (Global Memory)                     |
| Storage: ~/.raven/memory.md | Injected into System Prompt              |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| Tier 2: Active Working State (Project Memory)                           |
| Storage: ~/.raven/projects/<hash>/memory.md (4 Canonical Sections)      |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| Tier 3: Episodic Debug History & Cross-Project Vault                   |
| Storage: ~/.raven/debug_history.md, concept_vault/, other project memory |
| Retrieval: In-memory BM25 with Temporal Decay & Hit Count Weighting     |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| Tier 4: Knowledge / Concept Vault                                      |
| Storage: ~/.raven/concept_vault/*.md                                    |
| Retrieval: On-demand semantic/BM25 recall                               |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| Tier 5: Ephemeral Working Memory (In-Session Compaction)               |
| Micro (Sliding Window Truncation) + Macro (LLM Structural Summary)      |
+-------------------------------------------------------------------------+
```

---

## 3. Detailed Specifications of the 5 Architectural Upgrades

### 3.1. State-Reconciling Global Memory CRUD (Create, Read, Update, Delete)

#### 3.1.1. Problem
Currently, `save_to_memory` only checks `if bullet in content: return`. Over time, conflicting rules (e.g., "Do not run test cases" vs. "Always run unit tests before committing") accumulate in `~/.raven/memory.md`, confusing model steering.

#### 3.1.2. Solution
Convert `~/.raven/memory.md` into structured bullet points with unique categorical IDs or apply an atomic reconciliation pass before writing.

1. **Reconciliation Strategy:**
   When `save_to_memory(category, information)` is invoked:
   - Load existing entries under the matching category.
   - Run a fast zero-temperature reconciliation check using the fast model or rule-based semantic similarity:
     - **`NOOP`**: The information is already captured or strictly redundant.
     - **`APPEND`**: Distinct new fact or preference.
     - **`REPLACE`**: Replaces or contradicts an existing entry (identify line to overwrite).
     - **`MERGE`**: Refines or broadens an existing entry.
2. **Explicit Delete/Update Tooling:**
   Expose an internal helper `manage_global_memory(action: 'add' | 'update' | 'delete', target_pattern: str, new_content: str)` so obsolete entries can be cleanly pruned.

---

### 3.2. Search Corpus Partitioning & Cross-Project Recall

#### 3.2.1. Problem
`recall_memory` currently reads `~/.raven/memory.md` and indexes it into BM25. Because global memory is already injected in `messages[0]`, any match returned by `recall_memory` wastes 1 of the 3 top-K retrieval slots.

#### 3.2.2. Solution
1. **Exclude Global Memory:**
   Remove `~/.raven/memory.md` from the BM25 chunk collector.
2. **Include Inactive Project Vaults:**
   Index inactive project memory files (`~/.raven/projects/*/memory.md`) excluding the currently active project.
3. **Partitioned Scope:**
   The BM25 search corpus now indexes:
   - `~/.raven/debug_history.md` (Episodic past fixes)
   - `~/.raven/concept_vault/*.md` (Architectural explanations and design patterns)
   - `~/.raven/projects/<other_hash>/memory.md` (Cross-project architecture and constraints)

---

### 3.3. Automated Error-Triggered Recall Hook

#### 3.3.1. Problem
Developers and agents often encounter build errors or runtime tracebacks that have been solved previously. Relying on the LLM to actively decide to call `recall_memory` leads to duplicate troubleshooting effort.

#### 3.3.2. Solution
Integrate an automatic hook in `agent/core/hook_engine.py` or tool execution interceptor:

1. **Trigger Condition:**
   - Any `execute_command` output returning `exit_code != 0` or containing keywords: `Traceback`, `Error:`, `Exception:`, `FATAL:`, `npm ERR!`.
2. **Execution:**
   - Extract the core error line (last 3 lines of stderr or traceback header).
   - Execute an internal BM25 query against `debug_history.md`.
   - If top match score exceeds threshold `BM25_SCORE >= 4.5`:
     Append an episodic hint block to the tool result before returning to the model:
     ```markdown
     [SYSTEM EPISODIC RECALL: Similar error resolved previously]
     Match: {error_description}
     Solution: {solution}
     ```

---

### 3.4. Temporal Decay & Hit-Count Utility Scoring

#### 3.4.1. Problem
All entries in `debug_history.md` are flat markdown blocks without timestamps or hit counts. A deprecated fix from 12 months ago ranks equally with a modern fix.

#### 3.4.2. Storage Schema
Enhance `log_successful_debug` to store ISO (International Organization for Standardization) timestamps and an optional tag:

```markdown
<!-- entry: id=dbg_1740000000 ts=2025-02-19T10:00:00Z hits=1 -->
### Error: Failed to resolve module @tanstack/react-query
**Context:** React 19 migration
**Solution:** Update package.json to ^5.0.0 and install @tanstack/query-core.
```

#### 3.4.3. Hybrid Ranking Formula
When ranking episodic chunks:
```
Final_Score = BM25_Score * Temporal_Decay * Utility_Boost
```
Where:
- `Temporal_Decay = exp(-lambda * delta_days)` (with half-life = 90 days, `lambda = ln(2) / 90`)
- `Utility_Boost = 1.0 + 0.15 * log(hits + 1)`
- If an automated recall or manual recall leads to a successful turn, increment `hits`.

---

### 3.5. KV-Cache-Safe Mid-Session Memory Sync

#### 3.5.1. Problem
Currently, when `save_to_memory` or `update_project_memory` executes mid-conversation, the harness regenerates the system prompt and overwrites `messages[0]`. In modern LLM APIs (Anthropic, Gemini, OpenAI), KV cache prefixes depend on exact byte-for-byte prefix matching. Mutating `messages[0]` invalidates cache for the entire chat history.

#### 3.5.2. Solution
1. **Freeze `messages[0]` during active sessions:**
   The base system prompt in `messages[0]` remains frozen for the duration of the run.
2. **Ephemeral Context Injection:**
   When memory updates during an active session:
   - Update the disk markdown files immediately (`~/.raven/memory.md` or project memory).
   - Append an ephemeral system message to the tail of the message stream:
     ```json
     {"role": "user", "content": "[SYSTEM NOTIFICATION: Memory updated: <brief delta>]"}
     ```
   - On session reload, restart, or macro-compaction, re-read the disk files to produce a fresh immutable `messages[0]`.

---

## 4. Implementation Phasing & Work Items

| Phase | Component | Key Tasks |
|---|---|---|
| **Phase 1** | Search Corpus Partitioning | Remove global memory from BM25 corpus in `agent/tools/memory_tools.py`; add cross-project memory paths. |
| **Phase 2** | KV-Cache Safety | Decouple disk persistence from mid-session `messages[0]` mutation in `agent/main.py`. |
| **Phase 3** | Automated Error Recall | Wire error detector into `agent/tools/process_tools.py` / command execution to auto-inject past debug hits. |
| **Phase 4** | State Reconciliation | Add update/delete/deduplicate logic in `save_to_memory` to prevent duplicate global rules. |
| **Phase 5** | Temporal & Hit Scoring | Add metadata comments to `debug_history.md` and integrate decay multiplier into BM25 ranking. |
