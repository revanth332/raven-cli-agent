Project architecture:

 Updated the architecture map to reflect the new Textual multi-modal TUI interface (`agent/tui.py`), the codebase indexer (`agent/indexer.py`), the autonomous evals suite (`agent/evals.py`), and how they integrate into the system. 

 ```mermaid
graph TD
    subgraph CLI / Interface Layer
        M[agent/main.py] -->|CLI Commands & Entrypoint| T[agent/tui.py]
    end

    subgraph Core Logic Layer
        T -->|Asynchronous Interaction| L[agent/llm.py]
        M -->|Standard Console Loop| L
        L -->|Semantic Vector Search| I[agent/indexer.py]
    end

    subgraph Prompt Templates
        L -->|Loads Prompts| P{agent/prompts/}
    end

    subgraph System & Action Layer
        L -->|Direct File Mod & Command Exec| U[agent/utils.py]
        M -->|File/Command Utils| U
    end

    subgraph Testing & Validation
        E[agent/evals.py] -->|Autonomous Evals Suite| L
    end
```
