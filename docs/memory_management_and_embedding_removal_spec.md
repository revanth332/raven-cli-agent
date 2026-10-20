# Memory Management Overhaul & Embedding Removal Specification

## 1. Executive Decision: Should Raven Remove the Embedding / Vector DB Feature?

**Verdict: YES — Remove ChromaDB, Tree-sitter AST indexing, and Vertex AI embeddings (`agent/core/indexer.py` & `search_codebase`) completely.**

### Why Keeping Embeddings Is Not Worth It
1. **Industry Reality (Agentic Search > Vector RAG for Code):**
   Modern coding agents (Claude Code, OpenCode, Aider) do not use vector databases for local codebase retrieval. Raven already injects the full `{repo_map}` into the system prompt and has `find_file`, `search_file_content` (regex/literal grep with context lines), `read_file`, and an isolated `explore` subagent. Lexical grep + repo map + `explore` subagent is strictly superior for finding exact symbols, call sites, and imports with zero indexing lag.
2. **Hard Vendor Lock-In to Vertex AI:**
   Both `search_codebase` (`agent/core/indexer.py`) and `recall_memory` (`agent/tools/memory_tools.py`) hard-check `if not embedding_model or not use_vertex_ai(): return "Tool is not supported."`. Whenever Raven runs on OpenRouter, standard Gemini API keys, or custom OpenAI presets via `/connect`, the entire vector subsystem is dead weight while still consuming tool-schema tokens on every single turn.
3. **Massive Dependency & Startup Bloat:**
   `chromadb` (which pulls in `onnxruntime`, `sqlite/hnswlib`, `posthog`, `grpc`, etc.) and `tree-sitter-*` packages exist in `pyproject.toml` **solely** to power `indexer.py` and `memory_tools.py`. Removing them cuts dependency footprint, eliminates `~/.raven/vector_db/` disk bloat, and removes `RAVEN_EMBEDDING_MODEL` configuration complexity.
4. **Synchronous Latency & Stale Chunk Bugs:**
   Because `index_project()` and `index_episodic_memory()` run synchronously inside `search_codebase()` and `recall_memory()`, the first call on a modified project blocks the agent turn on network calls to Vertex AI `text-embedding-005`. Furthermore, ChromaDB's `upsert()` leaves orphaned tail chunks (`idx N..M`) whenever a file shrinks.
5. **Episodic Memory (`debug_history.md` & `concepts/*.md`) Does Not Need Vector Embeddings:**
   Personal debug logs and documented concepts are small local markdown collections (typically `< 100 KB`). A zero-dependency, pure-Python **BM25 / Lexical Token Scorer** over `chunk_debug_history()` and `concepts/*.md` executes in `< 2ms`, works across **100% of providers**, requires zero API calls, and never suffers from vector index drift.

---

## 2. Scope of Architectural Fixes

| ID | Problem / Flaw | Target Module(s) | Fix Summary |
| :--- | :--- | :--- | :--- |
| **M-01** | Premature Auto-Compaction before Micro-Compaction | `agent/core/llm.py` | Run `prune_message_payload()` **before** counting tokens for `should_auto_compact()`. |
| **M-02** | Vertex-Locked Vector DB & `search_codebase` Dead Weight | `agent/core/indexer.py`, `agent/tools/tool_registry.py`, `agent/core/subagent_manager.py`, `pyproject.toml` | Delete `agent/core/indexer.py` and `search_codebase` tool; replace ChromaDB in `recall_memory` with a fast local BM25/keyword scorer. |
| **M-03** | Mid-Session System Prompt Staleness (`self.messages[0]`) | `agent/core/llm.py`, `agent/tools/memory_tools.py` | Add a live system prompt refresh hook so updates to Global or Project Memory immediately update `self.messages[0]["content"]`. |
| **M-04** | Foreground `patch_file` Friction for Project Memory | `agent/tools/memory_tools.py`, `agent/prompts/system_prompt.md`, `agent/core/safety.py` | Replace generic `patch_file` instructions for project memory with a dedicated, auto-approved `update_project_memory` tool. |
| **M-05** | Append-Only Global Memory Bloat & Duplication | `agent/tools/memory_tools.py`, `agent/core/compaction.py`, `agent/prompts/compaction_prompt.md` | Deduplicate/compact `global_memory.md` when it exceeds token bounds and prevent `project_memory` from duplicating global constraints. |
| **M-06** | Destructive Conversation Compaction Without Backup | `agent/core/llm.py`, `agent/core/session_manager.py` | Archive pre-compaction message history snapshot (or fork point) before overwriting `self.messages` during `compact_history()`. |

---

## 3. Detailed Technical Specifications

### M-01: Fix Auto-Compaction vs. Micro-Compaction Ordering (`agent/core/llm.py`)

**Current Defect:**
In `AgentChatSession.send_message_stream()` (`agent/core/llm.py:401-433`), `count_tokens(self.messages)` runs on the raw, unpruned message list *before* `prune_message_payload()` strips bulky historical tool outputs and base64 images. Large `read_file` outputs from 3 turns ago inflate `current_tokens` past `60,000`, triggering lossy LLM summarization (`self.compact_history()`) even when the actual outbound payload is `< 15,000` tokens.

**Required Implementation:**
1. In `send_message_stream()`, execute `prune_message_payload(self.messages, ...)` **first** to produce `messages_to_send`.
2. Compute `effective_tokens = count_tokens(messages_to_send, self.model_name)`.
3. Pass `effective_tokens` into `should_auto_compact(effective_tokens, threshold=threshold, message_count=len(self.messages))`.
4. If `should_auto_compact` returns `True`, run `self.compact_history()` and re-compute `messages_to_send = prune_message_payload(self.messages, ...)`.

---

### M-02: Remove ChromaDB / Vertex Embeddings & Implement Provider-Agnostic `recall_memory`

**Current Defect:**
`agent/core/indexer.py` and `get_episodic_vector_db()` in `agent/tools/memory_tools.py` require `chromadb`, `tree-sitter-*`, and Vertex AI (`use_vertex_ai()`).

**Required Implementation:**
1. **Remove Codebase Vector Indexer:**
   - Delete `agent/core/indexer.py` and `tests/test_embedding_tools.py`.
   - Remove `search_codebase` from:
     - `agent/tools/tool_registry.py` (`raven_tools` schema and ` available_functions` map)
     - `agent/core/subagent_manager.py` (`EXPLORE_SYSTEM_PROMPT`, `GENERAL_SYSTEM_PROMPT`, and subagent tool lists)
     - `agent/prompts/system_prompt.md` (`## SEMANTIC CODE SEARCH` section and loop prevention references)
     - `agent/terminal_ui/chat_message.py` (`tool_name == "search_codebase"` special case)
   - Remove `RAVEN_EMBEDDING_MODEL` / `EMBEDDING_MODEL` references from `agent/core/settings.py`.
   - Remove `chromadb`, `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript`, and `tree-sitter-typescript` from `pyproject.toml`.
2. **Replace ChromaDB in `recall_memory(query: str)` (`agent/tools/memory_tools.py`):**
   - Remove `get_episodic_vector_db()` and `index_episodic_memory()`.
   - Implement a lightweight, pure-Python lexical/BM25 ranking function `_search_episodic_chunks(query: str, top_k: int = 3) -> list[dict]`:
     - Collect chunks on-the-fly from:
       - `~/.raven/debug_history.md` via `chunk_debug_history()`
       - `~/.raven/concepts/*.md` via `chunk_markdown_file()`
     - Note: Exclude `global_memory.md` from `recall_memory` because `global_memory.md` is already injected verbatim into the system prompt on every turn.
     - Tokenize `query` and each chunk into lowercase alphanumeric terms (stripping common English stopwords), score via BM25 + exact substring/phrase bonus, and return the top 3 matching chunks formatted with source file and chunk type.
     - Works offline, in `< 2ms`, on every LLM provider (OpenRouter, Gemini API, Vertex AI).

---

### M-03: Live System Prompt Refresh on Memory Mutation (`agent/core/llm.py`)

**Current Defect:**
`self.system_prompt` and `self.messages[0]` are constructed once in `AgentChatSession.__init__`. Any calls to `save_to_memory` or project memory updates during the session are invisible to `self.messages[0]` for the remainder of the session.

**Required Implementation:**
1. Extract a helper method `AgentChatSession.refresh_system_prompt()` in `agent/core/llm.py`:
   - Re-reads `get_memory_content()` and `get_project_memory_info()`.
   - Re-renders `self.system_prompt` from `prompts/system_prompt.md`.
   - Updates `self.messages[0]["content"] = self.system_prompt` in-place if `self.messages` starts with `role == "system"`.
2. Trigger `refresh_system_prompt()` automatically whenever a memory-mutating tool (`save_to_memory`, `update_project_memory`) completes in the tool execution loop.

---

### M-04: Dedicated `update_project_memory` Tool (`agent/tools/memory_tools.py`)

**Current Defect:**
The agent is instructed to use `patch_file` on `C:\Users\USER\.raven\memory\projects\<project>.md` to maintain `Current/Ongoing Tasks` and architecture notes. This causes fragile search-block mismatches, wastes `read_file` turns, and surfaces noisy file-patch diff blocks in the chat UI for background memory maintenance.

**Required Implementation:**
1. Create a dedicated tool `update_project_memory(section: str, content: str, mode: str = "replace")` in `agent/tools/memory_tools.py`:
   - `section`: Enum of `"Tech Stack & Runtime"`, `"Active Architecture & Key Modules"`, `"Critical Constraints, Preferences"`, or `"Current/Ongoing Tasks"`.
   - `mode`: `"replace"` (overwrites that specific markdown section's body) or `"append"` (appends bullet(s) to that section).
   - Parses `~/.raven/memory/projects/<project_name>.md` by `## <Section>` headers, updates only the targeted section, and writes atomically via `save_compacted_memory()`.
   - If the updated file exceeds `1,200` tokens (`should_compact_content`), runs `compact_content()` automatically.
2. Register `update_project_memory` in `agent/tools/tool_registry.py` with `"ignore_display": True` (like `save_to_memory`) and mark it as safe/auto-approved in `agent/core/safety.py`.
3. Update `agent/prompts/system_prompt.md` Instruction #2 to use `update_project_memory` instead of `patch_file`.

---

### M-05: Global Memory Deduplication & Compaction (`agent/tools/memory_tools.py` & `agent/core/compaction.py`)

**Current Defect:**
`save_to_memory(information, category)` blindly appends `\n-{category}: {information}` to `global_memory.md`. Duplicate or superseded facts (e.g., multiple `-career_prep:` entries) accumulate indefinitely. Additionally, `compact_content(project_memory)` does not know what is in `global_memory`, so compacted project memory retains duplicate global rules.

**Required Implementation:**
1. **Exact/Near-Duplicate Guard in `save_to_memory`:**
   - Before appending to `global_memory.md`, normalize whitespace/case and check if an identical entry already exists.
   - If `should_compact_content(global_memory_text, token_limit=800)` is `True` during `AgentChatSession.__init__` or after `save_to_memory`, compact and deduplicate `global_memory.md` using LLM distillation and atomic write (`save_compacted_memory`).
2. **Global-Aware Project Memory Compaction:**
   - Pass `global_memory` into `compact_content(project_memory, global_memory=global_memory)` so the compaction prompt strips any bullet point from `project_memory` that is already covered in `global_memory`.
3. **Remove `print(token_count)` Debug Leak:**
   - Remove the stray `print(token_count)` on line 14 of `agent/core/compaction.py` that leaks raw integers to stdout during TUI initialization.

---

### M-06: Non-Destructive Backup Before Session History Compaction (`agent/core/llm.py`)

**Current Defect:**
`AgentChatSession.compact_history()` overwrites `self.messages` with the summarized messages and immediately calls `self.save_session_state()`, permanently destroying the original turn-by-turn messages in `~/.raven/sessions/<session_id>.json`.

**Required Implementation:**
1. Before `self.compact_history()` overwrites `self.messages`, call `fork_session(current_session_data, new_title=f"{self.session_title} (Pre-Compaction Backup)")` or store a rolling `"archived_messages"` / backup file in `~/.raven/sessions/archive/<session_id>_<timestamp>.json`.
2. This guarantees zero permanent data loss if `SMALL_MODEL` drops a subtle detail during conversation distillation, while keeping the active `<session_id>.json` lightweight.

---

## 4. Files to Modify / Delete During Implementation

- **Delete:**
  - `agent/core/indexer.py`
  - `tests/test_embedding_tools.py`
- **Modify:**
  - `pyproject.toml` (remove `chromadb` and `tree-sitter*` dependencies)
  - `agent/core/compaction.py` (remove `print(token_count)`, add global-memory-aware compaction & global memory compaction helper)
  - `agent/core/llm.py` (fix `prune_message_payload` ordering before `should_auto_compact`, add `refresh_system_prompt()`, archive session before compaction)
  - `agent/tools/memory_tools.py` (replace ChromaDB with local BM25 `recall_memory`, add `update_project_memory`, deduplicate `save_to_memory`)
  - `agent/tools/tool_registry.py` (remove `search_codebase`, add `update_project_memory`)
  - `agent/core/safety.py` (auto-approve `update_project_memory`)
  - `agent/core/subagent_manager.py` (remove `search_codebase` from `explore` and `general` subagents)
  - `agent/prompts/system_prompt.md` (remove `search_codebase` section, update instruction #2 to use `update_project_memory`)
  - `agent/prompts/compaction_prompt.md` (enforce stripping entries that duplicate `global_memory`)
  - `agent/terminal_ui/chat_message.py` (remove `search_codebase` formatting check)
  - `agent/core/settings.py` (clean up `EMBEDDING_MODEL` defaults)
