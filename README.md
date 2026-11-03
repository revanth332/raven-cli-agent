# Raven

## 🚀 Overview

**Raven** is an autonomous personal AI developer agent and CLI assistant designed for full-stack software engineering. Built on top of Python, Textual, and modern LLM APIs (Google GenAI, OpenAI, and Vertex AI), Raven assists with coding, debugging, planning, system cartography, image generation, and workflow automation.

---

## ✨ Key Features

- **🖥️ Multi-Modal Terminal UI (TUI):** A custom Textual-based terminal workspace featuring real-time response streaming, animated loaders, theme customization, sidebar navigation, dynamic model selection, and mouse-selection support.
- **🤖 Autonomous Subagent Delegation:** Offload heavy exploration, git operations, commit reporting, or isolated scripts to lightweight, specialized subagents (`explore`, `git_ops`, `reporter`, `general`) without cluttering primary session context.
- **🛠️ Rich Tool Ecosystem:**
  - **File Operations:** Targeted code patching (`patch_file`), safe file creation, and chunk-based pagination.
  - **Git Operations:** Automated diff analysis, staging, and lowercase commit generation.
  - **Process Supervision:** Manage long-running dev servers and daemons via non-blocking background process tools.
  - **Web Intelligence:** Integrated web search and web page content extraction.
  - **Image Generation:** Multi-model image generation with facial preservation and reference image conditioning.
  - **Interactive Questionnaires:** Structured terminal decision modals for trade-offs and architectural choices.
- **⚡ Dynamic Model Registry & Provider Presets:** Switch dynamically across Gemini 2.5 / 3 (Flash & Pro) and OpenAI (GPT-4o, o3-mini) across standard and Vertex AI providers.
- **🧠 Intelligent Memory & Context Compaction:** Long-term memory persistence for user preferences, facts, and debug fixes, coupled with automated token-aware context compaction and session forking.
- **📊 Usage Tracking & Cost Analytics:** Live token tracking (prompt, cached, completion), model latency analytics, and HTML dashboard export.
- **🧩 Extensible Skills:** Modular global and project-specific skills in file and folder formats.

---

## 🛠️ Tech Stack

- **Runtime:** Python >= 3.10
- **TUI & CLI:** [Textual](https://textual.textualize.io/), [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/)
- **LLM Integrations:** `google-genai`, `openai`
- **Search & Scraping:** `ddgs`, `playwright`
- **Imaging & Utilities:** `pillow`, `tiktoken`, `python-dotenv`

---

## ⚙️ Prerequisites

- **Python 3.10+**
- A package manager such as `uv`, `pip`, or `poetry`.
- API keys for Google GenAI (`GEMINI_API_KEY`) and/or OpenAI (`OPENAI_API_KEY`).

---

## 💻 Installation

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd my-cli-agent
   ```

2. **Install the package and dependencies:**
   ```bash
   pip install -e .
   ```

3. **Configure Environment Variables:**
   ```env
   RAVEN_BASE_URL=
   RAVEN_USE_VERTEX_AI=
   RAVEN_MODEL=
   RAVEN_SMALL_MODEL=
   RAVEN_IMAGE_MODEL=
   ```

4. **Connect & Select Models In-App (`/connect`):**
   Alternatively, you can configure providers and start using models directly inside the TUI without manually editing environment variables:
   - Launch Raven (`raven` or `raven tui`) and run the `/connect` command in the prompt.
   - Choose an existing provider preset or create a new custom preset (**OpenAI-Compatible Endpoint** such as OpenRouter, OpenAI, Ollama, or **Google Vertex AI**).
   - Enter your **Base URL** and **API Key** (or use Google Cloud ADC for Vertex AI), then click **Connect** or **Save & Connect**.
   - Select your primary model in the model selection modal that opens automatically to start chatting immediately.

---

## ▶️ Usage

Once installed, Raven can be launched via the `raven` command:

### Launch Terminal UI (Recommended)
```bash
raven
# or
raven tui
```

### Interactive CLI Chat
```bash
raven chat
```

### Specialized CLI Commands

| Command | Description |
|---|---|
| `raven tui` | Launches the full Textual multi-modal terminal UI. |
| `raven debug` | Initiates debugging session or accepts piped error logs (`cat error.log \| raven debug`). |
| `raven review` | Reviews local code changes or files for potential bugs, security issues, and style. |
| `raven plan` | Generates implementation plans and system architectures before coding. |
| `raven commit` | Inspects staged git diffs and creates automated commit messages. |
| `raven report` | Generates structured project progress reports for chosen time periods. |
| `raven config` | Inspects or sets agent configuration key-value pairs (`raven config --set key=value`). |
| `raven eval` | Runs the autonomous evaluation suite to verify patch and tool accuracy. |
| `raven load` | Previews the interactive TUI spinner and loader gallery. |

---

## 💬 TUI Slash Commands

Inside the interactive TUI, type `/` in the prompt to access commands:

- `/connect` - Configure LLM provider presets, Base URL, API key, and models dynamically.
- `/models` - Open the dynamic model selector modal.
- `/skills` - Open and manage loaded skills.
- `/subagents` - View active subagents and task delegation settings.
- `/sessions` - Switch, create, or manage active chat sessions.
- `/fork` - Fork the current conversation branch.
- `/checkpoints` - View or revert to prior session checkpoints.
- `/usage` - Open the token tracking and cost analytics dashboard.
- `/compact` - Manually trigger conversation compaction.
- `/report` - Run progress reporter.
- `/commit` - Run git commit specialist.
- `/image <prompt>` - Generate images directly from chat.
- `/clear` - Clear the current chat view.

---

## 🤝 Contributing

1. Fork the repository and create your feature branch (`git checkout -b feature/my-feature`).
2. Commit your changes.
3. Push to the branch and open a Pull Request.
