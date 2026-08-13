Project architecture:

 Raven CLI Agent architecture diagram detailing the TUI layout, permission bar subsystem, and core agent modules. 

 ```mermaid
graph TD
    UI[agent/terminal_ui/app.py] -->|renders| Input[agent/terminal_ui/chat_input.py]
    UI -->|renders| Sidebar[agent/terminal_ui/sidebar.py]
    UI -->|mounts| PermBar[agent/terminal_ui/permission_box.py]
    UI -->|mounts| Modals[Modal Dialogs]
    Modals --> ModelModal[model_select_modal.py]
    Modals --> SessionModal[session_select_modal.py]

    UI -->|triggers| LLM[agent/core/llm.py]
    LLM -->|invokes| Registry[agent/tools/tool_registry.py]
    Registry --> FileTools[agent/tools/file_tools.py]
    Registry --> GitTools[agent/tools/git_tools.py]
    Registry --> WebTools[agent/tools/web_tools.py]
    Registry --> MemTools[agent/tools/memory_tools.py]
    
    LLM -->|evaluates| Safety[agent/core/safety.py]
    LLM -->|persists| SessMgr[agent/core/session_manager.py]
    LLM -->|tracks| Usage[agent/core/usage_tracker.py]
```
