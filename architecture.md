Project architecture:

 Raven CLI Agent modular architecture featuring Textual TUI, Slash Command Dispatcher (including deterministic Session Exporter for Markdown/JSON/HTML transcripts with base64 sanitization and collapsible tool timelines), LLM Session Orchestration, 4-tier Memory & Compaction Engine, Isolated Subagent Delegation, and Loop Safeguards. 

 ```mermaid
graph TD
    Entry[Main Entrypoint] -->|Launches| TUI[Terminal UI App]
    TUI -->|Dispatches Commands| SlashReg[Slash Command Registry]
    SlashReg -->|Triggers Export| Exporter[Session Exporter Engine]
    Exporter -->|Reads Active State| SessionMgr[Session Manager]
    Exporter -->|Writes .md / .json / .html| WorkspaceFS[(Workspace File System)]
    Exporter -->|Copies Path| Clipboard[System Clipboard]
    TUI -->|Manages Turns & Streams| LLM[LLM Session Orchestrator]
    TUI -->|Enforces Loop Ceiling| LoopGuard[Adaptive Loop Guard]
    LLM -->|Micro & Macro Compaction| Compaction[Compaction Engine]
    LLM -->|Persists & Archives| SessionMgr
    LLM -->|Tracks Tokens & Latency| Usage[Usage Tracker]
    LLM -->|Loads Prompts & Memory| MemEngine[Memory Engine]
    TUI -->|Executes Tools| Registry[Tool Registry]
    Registry -->|Isolated Subagents| SubagentRunner[Subagent Runner]
    SubagentRunner -->|Resolves Presets| SubagentMgr[Subagent Manager]
```
