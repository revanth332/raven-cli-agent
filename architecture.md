Project architecture:

 Updated project architecture to reflect modular structure of agent tools, safety checking subsystem, global settings, and core agent modules. 

 ```mermaid
graph TD
    subgraph UI_Layer [Terminal UI Layer]
        Main[agent/main.py] -->|Launches| TUI[agent/terminal_ui/app.py]
        TUI -->|Renders| Input[agent/terminal_ui/chat_input.py]
        TUI -->|Renders| ModelSelect[agent/terminal_ui/model_select_modal.py]
        TUI -->|Renders| PermBox[agent/terminal_ui/permission_box.py]
    end

    subgraph Core_Layer [Core Agent Layer]
        TUI -->|Uses session| LLM[agent/core/llm.py]
        LLM -->|Resolves configuration| Settings[agent/core/settings.py]
        TUI -->|Checks safety| Safety[agent/core/safety.py]
        LLM -->|Vector Search| Indexer[agent/core/indexer.py]
    end

    subgraph Tools_Layer [Modular Agent Tools]
        LLM -->|Calls function| ToolRegistry[agent/tools/tool_registry.py]
        ToolRegistry -->|Registry| FileTools[agent/tools/file_tools.py]
        ToolRegistry -->|Registry| GitTools[agent/tools/git_tools.py]
        ToolRegistry -->|Registry| MemoryTools[agent/tools/memory_tools.py]
        ToolRegistry -->|Registry| MiscTools[agent/tools/miscellaneous_tools.py]
    end

    subgraph Prompt_Layer [Prompts & Evals]
        LLM -->|Loads| Prompts{agent/prompts/}
        Evals[agent/evals.py] -->|Evaluates| Main
    end
```
