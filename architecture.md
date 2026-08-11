Project architecture:

 Updated project architecture map to include Token, Context, and Cost Consumption Tracking modules (pricing, token_counter, usage_tracker, sidebar). 

 ```mermaid
graph TD
    App[agent/terminal_ui/app.py] -->|Layout & Render| Sidebar[agent/terminal_ui/sidebar.py]
    App -->|Chat Session| LLM[agent/core/llm.py]
    LLM -->|Token Accounting| Tracker[agent/core/usage_tracker.py]
    LLM -->|Count Tokens| Counter[agent/core/token_counter.py]
    Tracker -->|Pricing Matrix & Cost| Pricing[agent/core/pricing.py]
    Tracker -->|Persist Metrics| History[~/.raven/usage_history.json]
    App -->|Tool Execution| Registry[agent/tools/tool_registry.py]
    App -->|Safety Inspection| Safety[agent/core/safety.py]
    App -->|Settings Configuration| Settings[agent/core/settings.py]
```
