# Compatibility & Integration Report: Open Knowledge Format (OKF) in Raven CLI Agent

## Executive Summary

This report evaluates the feasibility, benefits, and architectural implications of adopting the **Open Knowledge Format (OKF)** for memory management in **Raven CLI Agent**.

OKF is an open specification published by Google Cloud in June 2026. It formalizes the **LLM-Wiki pattern** by structuring domain and agent knowledge as an interlinked tree of Markdown (`.md`) files enriched with **YAML frontmatter metadata**.

---

## 1. Raven's Current Memory Architecture

`raven-cli-agent` manages memory across several flat files stored in `~/.raven/`:

| Memory Type | Current File Path | Current Format | Description |
| :--- | :--- | :--- | :--- |
| **Global Memory** | `~/.raven/memory.md` | Flat Markdown bullet points | User preferences, personal tech stack |
| **Active Project Memory** | `~/.raven/projects/<project>.md` | Flat Markdown bullet points | Project setup, updates, architectural facts |
| **Concept Memory** | `~/.raven/concepts/<concept>.md` | Markdown files | Detailed guides and design patterns |
| **Debug History** | `~/.raven/debug_history.md` | Markdown sections | Resolved errors and solutions |
| **Session State** | `~/.raven/sessions/<session_id>.json` | JSON format | Session history and message logs |

### Current Context Assembly Flow
During session initialization (`AgentChatSession` in `agent/core/llm.py`), raw contents from `memory.md` and `projects/<project>.md` are loaded and injected via template placeholders (`{global_memory}`, `{project_memory}`) into `agent/prompts/system_prompt.md`.

---

## 2. Compatibility Analysis

### Key Alignments
- **Markdown Core:** Both Raven and OKF use plain text `.md` files as their storage baseline.
- **File System Native:** Memory resides locally under standard directories (`.raven/`), compatible with Git tracking.
- **Modular Architecture:** Raven's memory handlers are centralized in `agent/tools/memory_tools.py`, making refactoring straightforward without affecting core UI or LLM drivers.

### Discrepancies & Gaps
1. **Missing Frontmatter:** Raven's current tools (`save_to_memory`, `save_to_project_memory`) append raw bullet points without structured headers (`okf_version`, `id`, `type`, `tags`, `last_updated`).
2. **Flat Append vs. Interlinked Graph:** Current project memory appends all facts into a single file (`<project_name>.md`). As project context grows, this can inflate context size. OKF organizes topics into discrete interlinked modules using relative Markdown links (`[Link](./concept.md)`).
3. **Unstructured Context Loading:** Memory loading in `llm.py` performs simple string concatenation without metadata filtering or dynamic context selection.

---

## 3. Key Benefits of Adopting OKF

1. **Context & Token Optimization:** YAML metadata (`type`, `tags`, `summary`) enables selective context injection based on task relevance.
2. **Standardized Knowledge Graph:** Relative Markdown links turn flat memory into a structured graph that Raven can traverse.
3. **Interoperability:** Enables memory sharing with external AI tools, IDE extensions, or agents supporting the OKF specification.
4. **Auditability & Freshness:** Timestamped frontmatter headers (`last_updated`, `authors`) allow stale memory pruning.

---

## 4. Proposed OKF Schema for Raven

### Global / User Memory (`~/.raven/memory.md`)
```yaml
---
okf_version: "1.0"
id: "raven-global-memory"
title: "Global User Memory & Preferences"
type: "user_profile"
tags: ["user_preferences", "global_context"]
last_updated: "2026-08-12T15:30:00Z"
---

# Global User Memory

- **Preference:** Developer uses Windows OS with React, Node, and Python stack.
- **Preference:** Light theme corporate palette preferences.
```

### Project Memory (`~/.raven/projects/<project_name>.md`)
```yaml
---
okf_version: "1.0"
id: "project-raven-cli-agent"
title: "Raven CLI Agent Context"
type: "project_context"
tags: ["cli", "python", "ai_agent"]
last_updated: "2026-08-12T15:30:00Z"
related_concepts:
  - "../concepts/open_knowledge_format.md"
---

# Project Context: raven-cli-agent

- [2026-08-12T15:28:20] Merged feature/web-search branch into main.
```

---

## 5. Conclusion & Next Steps

Integrating OKF into Raven CLI Agent is highly feasible and requires minimal storage migration.

### Recommended Next Steps for Implementation:
1. Update `agent/tools/memory_tools.py` to write OKF-compliant YAML frontmatter headers.
2. Add a migration utility to convert legacy `.raven` memory files to OKF format.
3. Enhance `AgentChatSession` in `agent/core/llm.py` to parse YAML headers for selective context loading.
