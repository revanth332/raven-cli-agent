Project architecture:

 Added /fork command and session branching logic into session_manager and app.py 

 ```mermaid
graph TD
    subgraph Core Agent
        LLM[agent/core/llm.py]
        SessionManager[agent/core/session_manager.py]
        UsageTracker[agent/core/usage_tracker.py]
    end
    subgraph Terminal UI
        App[agent/terminal_ui/app.py]
        SlashCommands[agent/terminal_ui/slash_commands.py]
        SessionModal[agent/terminal_ui/session_select_modal.py]
    end
    
    User((User)) -->|Types /fork| SlashCommands
    SlashCommands -->|Triggers action| App
    App -->|Requests branch| SessionManager
    SessionManager -->|Creates isolated branch| SessionManager
    SessionManager -.->|Prevents cost inheritance| UsageTracker
    App -->|Updates UI| SessionModal
    SessionModal -->|Displays [Fork] badge| User
```
