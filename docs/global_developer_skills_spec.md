# Implementation Specification: Global Developer Skills Suite for Raven

## 1. Executive Summary

This specification defines the architecture, directory structure, trigger protocols, and operational contracts for Raven's global engineering skills suite. These skills give Raven domain-specific expertise as a Senior Principal Engineer across **React, Node.js, and Python** on Windows environments.

All skills adhere to the following non-negotiable principles:
1. **Zero Test Generation / Execution:** Strictly no automated unit tests, mocks, test fixtures, or test runners unless explicitly instructed by the user.
2. **Actionable, Brutally Honest Analysis:** Every audit, architecture review, and optimization proposal must cite line numbers, root mechanisms, concrete risks, and surgical patches. No generic tips, platitudes, or empty praise.
3. **Native Tool Integration:** Full exploitation of Raven's built-in tools (`ask_user` for interactive decision frontiers, `update_architecture_map` for Mermaid diagrams, `patch_file` for direct AST-level modifications, and `~/.raven/sandbox` for scratchpad execution).
4. **Emoji-Free Output:** Professional, terminal-first presentation without decorative symbols or emoji clutter.

---

## 2. Directory Layout & Storage Model

All skills defined in this specification are stored in the user's global skills directory (`~/.raven/skills/`) as folder-based skills to allow modular supporting references and zero-dependency helper scripts.

```text
~/.raven/skills/
├── grill-me/
│   └── SKILL.md                          (Existing: Adversarial plan interrogation)
├── code-reviewer/
│   ├── SKILL.md                          (Core instructions & review contracts)
│   └── references/
│       ├── security_checklist.md         (OWASP Top 10, Auth, Secrets, Injection)
│       └── antipatterns_catalog.md       (React, Node, Python anti-patterns)
├── system-architect/
│   ├── SKILL.md                          (System design, RFC template, Mermaid contracts)
│   └── references/
│       └── rfc_template.md               (Standard production RFC template)
├── perf-optimizer/
│   ├── SKILL.md                          (React rendering, Event Loop, DB query tuning)
│   └── references/
│       └── sql_indexing_rules.md         (B-Tree, GIN, composite indexes, EXPLAIN)
├── debug-detective/
│   ├── SKILL.md                          (Hypothesis-driven forensics, RCA framework)
│   └── references/
│       └── rca_investigation_log.md      (Investigation notebook template)
└── api-designer/
    ├── SKILL.md                          (Idempotency, Pagination, Webhooks, Error specs)
    └── references/
        └── error_contract.md             (Normalized RFC 7807 error schema)
```

---

## 3. Skill Specifications

### 3.1 `code-reviewer` (Adversarial Code Review & Security Audit)

- **Folder:** `~/.raven/skills/code-reviewer/`
- **Scope:** `global`
- **Triggers:** `review`, `code review`, `audit`, `security audit`, `pr review`, `diff review`
- **Description:** Ruthless static code review and security auditing for React, Node, and Python codebases. Detects vulnerabilities, concurrency bugs, async leaks, and anti-patterns without writing test cases.

#### Review Contract & Severity Classification
Every issue flagged must be categorized into standard engineering severities:
- **P0 - Blocker / Vulnerability:** Remote code execution, SQL/Command injection, authentication/authorization bypass, leaked credentials, critical data corruption, or unhandled promise crashes that take down the service.
- **P1 - Critical Bug / Correctness Flaw:** Concurrency race conditions, memory leaks, silent state mutation, unhandled edge cases in core domain logic, or broken backward compatibility.
- **P2 - Performance & Architectural Debt:** Unnecessary React re-renders, N+1 database queries, blocking operations in Node/Python async event loops, or tight coupling violating Single Responsibility.
- **P3 - Minor / Maintainability:** Missing type bounds, confusing naming conventions, dead code, or style inconsistencies.

#### Review Execution Protocol
1. **Scope Inspection:** When reviewing staged changes or PRs, use `get_git_diff` or inspect target files via `read_file`. Never review blindly from memory.
2. **Impact Analysis:** For every flagged issue, provide:
   - File path and exact line numbers.
   - Mechanism of failure (why it breaks under production concurrency/scale).
   - Concrete `patch_file` ready replacement block.
3. **No Test Generation:** Reviewers frequently try to write test files. Under this skill, Raven strictly forbids creating test files, relying instead on structural proof, AST checks, and code logic reasoning.

---

### 3.2 `system-architect` (Production RFC & Architecture Designer)

- **Folder:** `~/.raven/skills/system-architect/`
- **Scope:** `global`
- **Triggers:** `architect`, `system design`, `rfc`, `design system`, `schema design`, `plan architecture`
- **Description:** Production RFC and system architecture designer. Evaluates technical trade-offs, schemas, boundary contracts, and generates Mermaid system diagrams via update_architecture_map.

#### Core Deliverables
1. **RFC Document Generation:** Generates a structured Request for Comments (RFC) covering:
   - Problem Statement & Goals / Non-Goals.
   - Proposed Architecture & Component Boundaries.
   - Data Models & Persistence (Postgres, SQLite, MongoDB schemas with strict constraints).
   - Protocol & API Contracts.
   - Failure Modes, Fallback Strategies & Scalability Bottlenecks.
2. **Visual Mapping:** Autonomously executes `update_architecture_map` to generate or update the project's Mermaid.js architecture diagram.
3. **Interactive Decision Frontiers:** When facing ambiguous trade-offs (e.g., synchronous REST vs asynchronous message queue, document vs relational storage), Raven must invoke `ask_user` with structured options, pros/cons, and recommended defaults rather than dumping questions into chat.

---

### 3.3 `perf-optimizer` (Full-Stack Performance Surgeon)

- **Folder:** `~/.raven/skills/perf-optimizer/`
- **Scope:** `global`
- **Triggers:** `optimize`, `perf`, `profile`, `slow query`, `re-render`, `memory leak`, `bottleneck`
- **Description:** Full-stack performance optimization across React components, Node.js event loops, Python async runtimes, and database queries.

#### Operational Focus Areas
1. **React Optimization:**
   - Detects state placement flaws causing entire component subtrees to re-render.
   - Audits `useEffect`, `useCallback`, and `useMemo` dependency arrays for referential instability.
   - Recommends virtualization (`react-window`, `tanstack-virtual`) for large list renders.
   - Identifies layout thrashing and heavy CSS recalculations.
2. **Node.js & Python Async Runtime:**
   - Detects CPU-intensive synchronous operations blocking the single-threaded Node event loop (e.g., heavy crypto, large JSON parsing, unchunked regex).
   - Identifies Python GIL-bound async routines that should be offloaded to process pools (`concurrent.futures.ProcessPoolExecutor`).
   - Identifies memory retention from uncleaned event listeners, unclosed streams, or global caching dictionaries.
3. **Database & Persistence:**
   - Flags N+1 ORM query patterns in Prisma, TypeORM, SQLAlchemy, or Django ORM.
   - Analyzes query execution plans (EXPLAIN ANALYZE) to identify sequential scans on tables lacking composite/partial indexes.

---

### 3.4 `debug-detective` (Hypothesis-Driven Root Cause Investigator)

- **Folder:** `~/.raven/skills/debug-detective/`
- **Scope:** `global`
- **Triggers:** `debug`, `rca`, `root cause`, `investigate crash`, `trace error`, `stack trace`
- **Description:** Rigorous hypothesis-driven root-cause investigator for complex bugs, race conditions, subprocess hangs, and silent corruptions. Rejects superficial band-aids.

#### Investigation Framework
1. **Forensics First:**
   - Gather exact error traces, environment variables, OS limitations, and recent git history via `get_git_log`.
   - Never speculate without inspecting the actual code executing at the stack trace offset.
2. **Hypothesis Formulation & Falsification:**
   - Formulate 2 to 3 distinct, mutually exclusive hypotheses explaining the failure.
   - For each hypothesis, identify a definitive observation that confirms or falsifies it.
3. **Surgical Resolution:**
   - Reject band-aids (e.g., wrapping arbitrary code in empty `try...catch` blocks or adding arbitrary `sleep()` delays).
   - Apply the fix at the root structural layer using `patch_file`.
   - Document the incident using `log_successful_debug` to prevent regression.

---

### 3.5 `api-designer` (API Protocols, Idempotency & Contract Engineering)

- **Folder:** `~/.raven/skills/api-designer/`
- **Scope:** `global`
- **Triggers:** `api design`, `openapi`, `rest contract`, `endpoints`, `webhook design`, `contract`
- **Description:** End-to-end API protocol and interface designer for REST, GraphQL, and tRPC. Enforces idempotency, pagination standards, rate-limiting, and error normalization.

#### Standard API Engineering Contracts
1. **Idempotency Standards:**
   - Enforces `Idempotency-Key` headers on non-idempotent POST/PATCH mutation endpoints using distributed cache or atomic database leases.
2. **Pagination Consistency:**
   - Mandates cursor-based pagination (opaque `cursor` + `limit`) for frequently updated feeds to prevent page-drift anomalies inherent in `offset/limit`.
3. **Normalized Error Envelopes (RFC 7807):**
   - Standardizes error JSON payloads with `code`, `message`, `details` (field-level validation issues), and a trace `requestId`.
4. **Webhook Security:**
   - Enforces HMAC-SHA256 signature verification headers (`X-Signature`), timestamp replay windows (5-minute expiration), and constant-time string comparisons.
5. **Schema Validation:**
   - Implements strict validation schemas using Zod for TypeScript/Node or Pydantic v2 for Python.

---

## 4. Implementation Plan & Staging

The skills will be created sequentially in `~/.raven/skills/` using standard folder skill architecture:

1. **Phase 1: `code-reviewer`**
   - Create `~/.raven/skills/code-reviewer/SKILL.md`
   - Create `~/.raven/skills/code-reviewer/references/security_checklist.md`
   - Create `~/.raven/skills/code-reviewer/references/antipatterns_catalog.md`

2. **Phase 2: `system-architect`**
   - Create `~/.raven/skills/system-architect/SKILL.md`
   - Create `~/.raven/skills/system-architect/references/rfc_template.md`

3. **Phase 3: `perf-optimizer`**
   - Create `~/.raven/skills/perf-optimizer/SKILL.md`
   - Create `~/.raven/skills/perf-optimizer/references/sql_indexing_rules.md`

4. **Phase 4: `debug-detective`**
   - Create `~/.raven/skills/debug-detective/SKILL.md`
   - Create `~/.raven/skills/debug-detective/references/rca_investigation_log.md`

5. **Phase 5: `api-designer`**
   - Create `~/.raven/skills/api-designer/SKILL.md`
   - Create `~/.raven/skills/api-designer/references/error_contract.md`

6. **Phase 6: Verification & Dual-Scope Registry Check**
   - Verify all 5 skills are correctly parsed by `agent.core.skills_manager.load_skills()`.
   - Confirm proper trigger matching and zero test generation constraints.
