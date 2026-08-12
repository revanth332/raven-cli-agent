Project architecture:

 Architecture map updated to include agent/tools/web_tools.py for web search capabilities. 

 ```mermaid
graph TD
    subgraph CLI ["CLI & Entrypoint"]
        MAIN["agent/main.py"]
        TUI["agent/terminal_ui/app.py"]
    end

    subgraph CORE ["Core Engine"]
        LLM["agent/core/llm.py"]
        SAFETY["agent/core/safety.py"]
        SESS["agent/core/session_manager.py"]
        TOKENS["agent/core/token_counter.py"]
        USAGE["agent/core/usage_tracker.py"]
        INDEXER["agent/core/indexer.py"]
        SETTINGS["agent/core/settings.py"]
    end

    subgraph UI ["Terminal UI Components"]
        SIDEBAR["agent/terminal_ui/sidebar.py"]
        INPUT["agent/terminal_ui/chat_input.py"]
        MODAL_M["agent/terminal_ui/model_select_modal.py"]
        MODAL_S["agent/terminal_ui/session_select_modal.py"]
        PERM["agent/terminal_ui/permission_box.py"]
        THINK["agent/terminal_ui/thinking_loader.py"]
    end

    subgraph TOOLS ["Agent Tools"]
        REGISTRY["agent/tools/tool_registry.py"]
        FILE_TOOLS["agent/tools/file_tools.py"]
        GIT_TOOLS["agent/tools/git_tools.py"]
        MEM_TOOLS["agent/tools/memory_tools.py"]
        WEB_TOOLS["agent/tools/web_tools.py"]
        MISC_TOOLS["agent/tools/miscellaneous_tools.py"]
    end

    MAIN -->|Mounts TUI| TUI
    TUI -->|Composes UI| SIDEBAR
    TUI -->|Composes UI| INPUT
    TUI -->|Dispatches LLM Requests| LLM
    TUI -->|Manages Sessions| SESS
    LLM -->|Executes Tools| REGISTRY
    REGISTRY -->|Invokes| FILE_TOOLS
    REGISTRY -->|Invokes| GIT_TOOLS
    REGISTRY -->|Invokes| MEM_TOOLS
    REGISTRY -->|Invokes| WEB_TOOLS
    REGISTRY -->|Invokes| MISC_TOOLS
    LLM -->|Tracks Usage| USAGE

```
