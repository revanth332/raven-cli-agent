Project architecture:

 Added Two-Mode Subagent Architecture (SubAgentRunner, SubagentManager, and delegate_to_subagent tool) supporting direct slash commands (/report, /commit, /subagent) and autonomous agent delegation. 

 ```mermaid
graph TD
    subgraph Terminal UI
        App[agent/terminal_ui/app.py]
        ChatInput[agent/terminal_ui/chat_input.py]
        ChatMessage[agent/terminal_ui/chat_message.py]
        SlashCommands[agent/terminal_ui/slash_commands.py]
    end
    subgraph Core Engine
        LLM[agent/core/llm.py]
        SubagentMgr[agent/core/subagent_manager.py]
        SubagentRunner[agent/core/subagent_runner.py]
        UsageTracker[agent/core/usage_tracker.py]
    end
    subgraph Tools
        ToolRegistry[agent/tools/tool_registry.py]
        SubagentTools[agent/tools/subagent_tools.py]
    end

    User((User)) -->|Submits query or slash command| ChatInput
    ChatInput -->|Dispatches event| App
    App -->|Mode A: /report, /commit, /subagent| SubagentRunner
    App -->|Primary chat loop| LLM
    LLM -->|Calls delegate_to_subagent| ToolRegistry
    ToolRegistry -->|Invokes| SubagentTools
    SubagentTools -->|Mode B: Isolated delegation| SubagentRunner
    SubagentRunner -->|Resolves preset & model| SubagentMgr
    SubagentRunner -->|Records token usage| UsageTracker
    SubagentRunner -->|Streams timeline updates| ChatMessage
```
