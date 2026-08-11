Project architecture:

 Updated project architecture map to include Session Management modules (session_manager, session_select_modal) and slash commands (/new, /sessions, /switch). 

 ```mermaid
graph TD
    App[agent/terminal_ui/app.py] -->|Session Selection Modal| SessModal[agent/terminal_ui/session_select_modal.py]
    App -->|Layout & Render| Sidebar[agent/terminal_ui/sidebar.py]
    App -->|Chat Session| LLM[agent/core/llm.py]
    LLM -->|Session Persistence| SessMgr[agent/core/session_manager.py]
    SessMgr -->|Persist JSON| SessStore[~/.raven/sessions/*.json]
    LLM -->|Token Accounting| Tracker[agent/core/usage_tracker.py]
    LLM -->|Count Tokens| Counter[agent/core/token_counter.py]
    Tracker -->|Pricing Matrix & Cost| Pricing[agent/core/pricing.py]
    App -->|Tool Execution| Registry[agent/tools/tool_registry.py]
    App -->|Safety Inspection| Safety[agent/core/safety.py]
    App -->|Settings Configuration| Settings[agent/core/settings.py]
```
