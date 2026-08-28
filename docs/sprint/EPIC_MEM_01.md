# EPIC: MEM-01 — Agent Memory Architecture & Context Optimization

## 🎯 Executive Goal
Transform Raven's memory subsystem from an unbounded $O(N)$ append-only log into a high-density, bounded **Architectural State Engine** paired with **Semantic Retrieval (ChromaDB)** and **Automated State Compaction**.

---

## 🛑 Problem Statement
1. **Unbounded Context Bloat**: Every commit appends raw timestamped bullet points into `~/.raven/projects/{project}.md`, which is injected directly into the LLM system prompt on every turn.
2. **Context Pollution & Attention Degradation**: High-density architectural rules compete for attention against low-value git logs and minor debugging history.
3. **Temporal Contradictions**: Obsolete technical decisions persist alongside new decisions with no resolution mechanism.
4. **Duplication of Git**: The agent duplicates `git log` in markdown files, burning tokens and context window budget.

---

## 🏗️ Target Architecture: 3-Tier Distilled Memory Model

```
┌──────────────────────────────────────────────────────────────────┐
│ Tier 1: Active Working State (~500 - 1,000 tokens)               │
│ - Tech Stack & Runtime                                           │
│ - Active Architecture & Key Modules                              │
│ - Critical Constraints & Directives                              │
│ 👉 Injected directly into System Prompt. Strictly bounded.       │
├──────────────────────────────────────────────────────────────────┤
│ Tier 2: Automated Compaction / State Distillation Engine         │
│ - Triggers on token threshold or fact accumulation               │
│ - Synthesizes & replaces superseded decisions via LLM pass       │
│ 👉 Keeps Tier 1 dense, clean, and under token budget.            │
├──────────────────────────────────────────────────────────────────┤
│ Tier 3: Semantic Retrieval Store (ChromaDB Vector DB)            │
│ - Historical debug logs, concepts, deep session summaries        │
│ 👉 Queried dynamically on-demand via `recall_memory` tool.      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Roadmap & Story Map

| Ticket ID | Title | Estimate | Status |
| :--- | :--- | :--- | :--- |
| **MEM-101** | Prompt Directives Refactor & Legacy Schema Migration | 2 SP | 🟢 Done |
| **MEM-102** | Tool Registry Cleanup & Direct Patching Memory Integration | 2 SP | 🟢 Done |
| **MEM-103** | Automated Memory Compactor & Distillation Routine | 5 SP | 🟡 In Progress |
| **MEM-104** | Semantic Episodic Memory Tool (`recall_memory` via ChromaDB) | 3 SP | ⚪ Backlog |
| **MEM-105** | Unit Tests, Integration Benchmarks & Documentation | 2 SP | ⚪ Backlog |
