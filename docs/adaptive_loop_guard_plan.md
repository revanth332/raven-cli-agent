# Adaptive Agent Loop Guard Implementation Plan

## Goal

Replace the abrupt fixed 10-round stop with an adaptive execution budget that lets productive tasks finish while still preventing runaway tool loops.

## Policy

1. Keep 10 tool rounds as the soft budget.
2. At the soft budget, instruct the model to wrap up and allow at most two grace rounds for essential verification.
3. Force a tool-disabled final response after the grace rounds, 20 total rounds, 40 individual tool calls, or 3 consecutive no-progress rounds.
4. Count LLM tool rounds and individual tool calls separately.
5. Treat rounds containing only duplicate calls or tool errors as no-progress rounds.
6. Always let the model explain completed work, verification status, and remaining work before ending.
7. Expose budget values through Raven settings.

## Changes

- Extend `LoopGuard` with execution states, separate counters, grace-round tracking, and stagnation tracking.
- Add configurable limits to `Settings`.
- Allow `AgentChatSession.send_message_stream` to inject a temporary execution instruction and disable tools.
- Update CLI and TUI loops to use soft wrap-up and mandatory finalization.
- Expand loop-guard tests for soft limits, hard limits, tool budgets, and stagnation.

## Verification

Run:

```powershell
python -m uv run python -m pytest -q
```
