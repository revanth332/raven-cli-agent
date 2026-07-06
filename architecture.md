Project architecture:

 The core architecture follows a standard CLI agent pattern. `agent/main.py` acts as the entry point, routing commands to `agent/llm.py` for AI processing and to `agent/utils.py` for system interactions (like file operations and command execution). The `agent/llm.py` module depends heavily on the contextual prompts stored in the `agent/prompts/` directory. 

 ```mermaid
graph TD
    A[agent/main.py] -- Routes AI Commands --> B(agent/llm.py)
    A -- Uses for System Calls --> D(agent/utils.py)
    B -- Loads Prompts --> C{agent/prompts/}
    B -- Uses Utilities --> D
```
