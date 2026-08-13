# Open Knowledge Format (OKF) Integration Plan

## Overview & Scope

This plan transitions Raven CLI Agent's memory management to the Open Knowledge Format (OKF) specification by establishing standard YAML frontmatter headers, interlinked document trees, and tag-based metadata indexing across all global, project, concept, and debug history files. The architecture introduces a lightweight OKF parser/formatter module, backward-compatible automatic migration for legacy `.raven` text files, and metadata-aware context assembly for LLM chat sessions.

---

## Phase 1: Core OKF Parser & Serialization Layer

### Step 1.1: Implement OKF Document Parser and Serializer Module

- **Files Impacted**: `agent/core/okf_parser.py` (New), `pyproject.toml`
- **Objective**: Implement core utility functions (`parse_okf_document`, `format_okf_document`) using `PyYAML` to parse and serialize Markdown text with YAML frontmatter containing fields `okf_version`, `id`, `title`, `type`, `tags`, `last_updated`, and `related_concepts`.
- **Dependencies**: None.
- **Verification**: Run unit tests asserting that valid OKF files correctly return metadata dicts and body text, and that missing frontmatter falls back gracefully.

### Step 1.2: Build Legacy Memory Migration Utility

- **Files Impacted**: `agent/core/okf_parser.py`, `agent/tools/memory_tools.py`
- **Objective**: Add `migrate_legacy_memory_to_okf()` to automatically inspect existing `~/.raven/memory.md` and `~/.raven/projects/*.md` files, inject compliant OKF 1.0 frontmatter headers if missing, and save backup files (`.md.bak`).
- **Dependencies**: Step 1.1
- **Verification**: Run migration utility against a mock legacy `.raven` directory and verify generated files contain valid frontmatter while preserving all pre-existing bullet points.

---

## Phase 2: Memory Tools Refactoring & OKF Specification Compliance

### Step 2.1: Refactor Global and Active Project Memory Handlers

- **Files Impacted**: `agent/tools/memory_tools.py`
- **Objective**: Update `get_memory_content()`, `get_project_memory()`, `save_to_memory()`, and `save_to_project_memory()` to parse OKF headers, update the `last_updated` ISO timestamp on edits, and append structured entries cleanly.
- **Dependencies**: Step 1.1, Step 1.2
- **Verification**: Call `save_to_memory()` and `save_to_project_memory()` in a python test script and verify generated files match OKF schema with updated timestamps.

### Step 2.2: Standardize Concept Documentation and Debug Logging Tools

- **Files Impacted**: `agent/tools/memory_tools.py`
- **Objective**: Upgrade `save_concept()` and `log_successful_debug()` to format concept documents (`~/.raven/concepts/`) and debug history logs as discrete OKF documents with `type: concept` and `type: debug_log`.
- **Dependencies**: Step 2.1
- **Verification**: Trigger `save_concept()` and inspect the target file in `~/.raven/concepts/` to confirm YAML header formatting and concept interlinking tags.

---

## Phase 3: Context Assembly & Tool Registry Integration

### Step 3.1: Upgrade System Prompt Assembly Engine

- **Files Impacted**: `agent/core/llm.py`, `agent/prompts/system_prompt.md`
- **Objective**: Update `AgentChatSession.__init__` in `llm.py` to parse OKF metadata, strip raw YAML frontmatter before injecting body text into `{global_memory}` and `{project_memory}`, and expose frontmatter tags to system instructions.
- **Dependencies**: Phase 2
- **Verification**: Instantiate `AgentChatSession()` and assert that `self.system_prompt` contains clean memory text without raw YAML delimiter noise.

### Step 3.2: Update Tool Registry Schemas for AI Function Calling

- **Files Impacted**: `agent/tools/tool_registry.py`
- **Objective**: Update tool docstrings and parameter JSON schemas for `save_to_memory`, `save_to_project_memory`, and `save_concept` in `TOOL_REGISTRY` to support optional metadata attributes (`tags`, `title`).
- **Dependencies**: Step 3.1
- **Verification**: Inspect `raven_tools` generated schema output to ensure parameter descriptions accurately reflect OKF metadata options.

---

## Phase 4: Automated Testing & Verification Suite

### Step 4.1: Implement OKF Unit Test Suite

- **Files Impacted**: `tests/test_okf_memory.py` (New)
- **Objective**: Create comprehensive unit tests covering OKF parsing, legacy migration, timestamp updates, tag filtering, and prompt context injection.
- **Dependencies**: Phase 1, Phase 2, Phase 3
- **Verification**: Run `python -m unittest discover tests` and ensure all test cases pass with 100% success rate.

---

## Cross-Cutting Concerns

- **Security/Auth**: Sanitize frontmatter input fields and enforce strict canonical path checking (`Path.resolve()`) within `~/.raven/` to prevent path traversal when navigating interlinked concepts.
- **Performance**: Cache parsed YAML metadata in memory to avoid redundant disk I/O and YAML parsing during multi-turn LLM generation loops.
- **Rollback Plan**: Automatic backup creation (`.md.bak`) during initial migration allows instant manual or programatic rollback if frontmatter parsing fails.
