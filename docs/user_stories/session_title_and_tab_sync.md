# User Stories: Intelligent Session Titling & Terminal Tab Title Sync

## Epic Overview
Improve session identity and window management in Raven by replacing raw 32-character string truncation with LLM-generated descriptive session titles (3-5 words), updating the sidebar dynamically, and syncing the session title directly to the terminal tab/window title in CMD, PowerShell, and Windows Terminal.

---

## User Stories

### Story 1: AI-Generated Descriptive Session Titles
**ID:** `US-SESSION-001`  
**Priority:** High  
**Status:** Completed  

#### Description
As a user, I want my chat session title to be intelligently generated based on the intent of my initial question rather than simply being a truncated 32-character string of my prompt, so that my sessions list and sidebar display meaningful topics (e.g., "Docker Deployment Setup", "Fixing React State Leak").

#### Acceptance Criteria
1. **Title Generation Worker:** Implement `generate_ai_session_title(user_query: str, assistant_response: str = None, fallback_model: str = None) -> str` using `gemini-2.5-flash-lite` as the primary model and the active selected model as the fallback. Prompts the model for a concise 3-5 word title with temperature 0.2 and no quotes/backticks.
2. **Session Persistence:** When the title is generated, update `session_title` on `chat_session` and persist it via `save_session` in `~/.raven/sessions/<id>.json`.
3. **Sidebar Live Update:** Dynamically refresh the sidebar component's session name widget immediately once the title is generated, without requiring a restart or manual switch.
4. **Fallback:** If title generation fails across both models, fall back safely to cleaned truncated query text.
5. **Unit Tests:** Add unit tests verifying title generation logic, prompt construction, model fallbacks, and metadata persistence.

---

### Story 2: Terminal Window & Tab Title Synchronization
**ID:** `US-SESSION-002`  
**Priority:** Medium  
**Status:** Completed  

#### Description
As a user working across multiple terminal tabs or Windows, I want the active session title to be reflected in the tab/window title of CMD, PowerShell, or Windows Terminal, so that I can easily identify and switch between active Raven agent tasks.

#### Acceptance Criteria
1. **Textual Title Integration:** Update `self.title` on `RavenTUI` whenever a session is loaded, switched, or when an AI title is generated (`Raven - <session_title>`).
2. **ANSI Terminal Escape Sequence:** Emit standard OSC escape sequence `\033]0;Raven - <session_title>\007` to ensure compatibility across Windows Terminal, ConHost CMD, PowerShell, and macOS/Linux terminals.
3. **Lifecycle Synchronization:** Update the tab title on app startup, when switching sessions (`/switch` / `/sessions`), when starting fresh (`/new`), and after AI title generation finishes.
4. **Unit Tests:** Add unit tests verifying tab title formatting and update triggers.
