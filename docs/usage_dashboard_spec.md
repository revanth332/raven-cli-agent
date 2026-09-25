# Specification: Usage Analytics & HTML Dashboard (`/usage`)

## 1. Overview & Objectives

This specification outlines the data aggregation, storage schema, HTML dashboard generation, and CLI integration for tracking daily LLM usage across models and visualizing trends with interactive graphs.

### Objectives
- **Daily Aggregated Analytics:** Record and aggregate prompt tokens, completion tokens, total tokens, request count, and estimated cost per model per day.
- **Standalone HTML Dashboard (`usage_report.html`):** A single static HTML file with modern dark UI and interactive charts (Chart.js) that loads dynamic data seamlessly via `<script src="usage_data.js">` without CORS/file protocol restrictions.
- **Zero-Friction Access:** Introduce the `/usage` slash command to launch the dashboard directly in the user's default browser while printing a quick summary in the terminal.

---

## 2. Architecture & Data Flow

```mermaid
graph TD
    subgraph Agent Runtime
        LLM[LLM Turn Complete] -->|tokens, cost, model| UsageTracker[UsageTracker Subsystem]
        UsageTracker -->|update & aggregate| MemoryStore[Thread-Safe Daily Usage Store]
        MemoryStore -->|atomic write| JSONFile[~/.raven/usage_history.json]
        MemoryStore -->|export JS object| JSFile[~/.raven/usage_data.js]
    end

    subgraph User Experience
        Command[/usage Slash Command] --> Launcher[Usage Dashboard Launcher]
        Launcher --> CheckHTML{usage_report.html exists?}
        CheckHTML -->|No| InitHTML[Generate usage_report.html template]
        CheckHTML -->|Yes| OpenBrowser[webbrowser.open(usage_report.html)]
        InitHTML --> OpenBrowser
        OpenBrowser --> BrowserUI[Interactive Browser Dashboard]
        BrowserUI -->|imports| JSFile
    end
```

---

## 3. Data Schema

### 3.1. `usage_data.js` & `usage_history.json`
```json
{
  "2025-05-10": {
    "google/gemini-3-flash-preview": {
      "prompt_tokens": 12000,
      "completion_tokens": 3500,
      "tokens": 15500,
      "requests": 42,
      "cost": 0.00185
    },
    "openrouter/free": {
      "prompt_tokens": 2000,
      "completion_tokens": 800,
      "tokens": 2800,
      "requests": 6,
      "cost": 0.0
    }
  }
}
```

---

## 4. Components & Implementation Plan

### 4.1. Core Usage Tracker (`agent/core/usage_tracker.py`)
- Maintain `self.daily_usage: Dict[str, Dict[str, Dict[str, Any]]]`.
- In `record_turn(prompt_tokens, completion_tokens, model_name)`:
  - Calculate `today = datetime.now().strftime("%Y-%m-%d")`.
  - Update `daily_usage[today][model_name]` (`prompt_tokens`, `completion_tokens`, `tokens`, `requests`, `cost`).
  - Persist to both `usage_history.json` and `usage_data.js` (`window.USAGE_DATA = ...;`).
- Add helper `ensure_dashboard_files()` and `get_dashboard_path()`.

### 4.2. HTML Dashboard Template (`usage_report.html`)
- Clean, responsive dark theme matching Raven CLI palette (`#0F172A`, `#1E293B`, `#06B6D4`, `#10B981`).
- Top Metric Cards: Total Tokens, Total Requests, Total Cost ($), Most Used Model.
- Chart 1: **Daily Token Consumption** (Stacked Bar per Model).
- Chart 2: **Daily Request Frequency** (Grouped Bar / Line per Model).
- Interactive Data Table: Filterable daily metrics breakdown.

### 4.3. CLI Command & Terminal Integration (`agent/terminal_ui/app.py`)
- Register `/usage` in `SLASH_COMMANDS` with autocomplete.
- Handle `/usage` trigger:
  - Invokes `usage_tracker.ensure_dashboard_files()`.
  - Launches `webbrowser.open()` pointing to `~/.raven/usage_report.html`.
  - Mounts a brief terminal summary card confirming dashboard launch.
