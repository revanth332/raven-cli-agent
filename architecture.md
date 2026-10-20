Project architecture:

 Raven CLI Agent modular architecture with Textual TUI, OpenAI/OpenRouter/Vertex LLM session orchestration, provider-agnostic 4-tier memory & compaction engine (local BM25 episodic recall, atomic section-level project memory updates, micro-compaction + archived macro-compaction), isolated subagent delegation, and tool execution loop safeguards. 

 ```mermaid
graph TD
    Entry[agent/main.py] -->|Launches| TUI[agent/terminal_ui/app.py]
    TUI -->|Manages Turns & Streams| LLM[agent/core/llm.py]
    TUI -->|Enforces Loop Ceiling| LoopGuard[agent/core/loop_guard.py]
    LLM -->|Micro & Macro Compaction| Compaction[agent/core/compaction.py]
    LLM -->|Persists & Archives| SessionMgr[agent/core/session_manager.py]
    LLM -->|Tracks Tokens & Latency| Usage[agent/core/usage_tracker.py]
    LLM -->|Loads Prompts & Memory| MemTools[agent/tools/memory_tools.py]
    TUI -->|Executes Tools| Registry[agent/tools/tool_registry.py]
    Registry -->|File & Grep Ops| FileTools[agent/tools/file_tools.py]
    Registry -->|Git Ops| GitTools[agent/tools/git_tools.py]
    Registry -->|BM25 Recall & Project Memory| MemTools
    Registry -->|Isolated Subagents| SubagentRunner[agent/core/subagent_runner.py]
    SubagentRunner -->|Resolves Presets| SubagentMgr[agent/core/subagent_manager.py]
```
