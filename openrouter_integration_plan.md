# Plan: OpenRouter Integration for Raven CLI

This document outlines the step-by-step implementation plan to integrate **OpenRouter** models alongside standard **Gemini** models in the Raven CLI application, without introducing heavy framework bloat.

---

## 1. Objectives
- Enable access to top-tier non-Gemini models (e.g., Claude 3.5 Sonnet, GPT-4o, DeepSeek, Llama 3) via **OpenRouter**.
- Keep startup latency extremely low (< 50ms overhead).
- Ensure **100% backward compatibility** with the current custom CLI terminal loops, spinners, and tool permission gates in `agent/main.py`.
- Keep changes localized, clean, and robust.

---

## 2. Dependencies
- Install the official **`openai`** Python SDK (OpenRouter has complete OpenAI-compatible endpoints).
- Patched `pyproject.toml` to list `openai` as a dependency.
- Required Environment Variable: `OPENROUTER_API_KEY` or `OPENAI_API_KEY` defined in `.env`.

---

## 3. Step-by-Step Implementation Strategy

### Step 3.1: Define OpenAI Function Call Schemas
In `agent/llm.py`, implement `get_openai_tools()` which returns a list of JSON schemas corresponding to the 15 tools in our `TOOL_REGISTRY`. This informs OpenRouter models exactly how to construct function call arguments.

Tools to declare:
1. `save_to_memory`
2. `save_to_project_memory`
3. `log_successful_debug`
4. `save_concept`
5. `find_file`
6. `patch_file`
7. `read_file`
8. `create_file`
9. `execute_command`
10. `get_current_timestamp`
11. `update_architecture_map`
12. `run_ui_test`
13. `search_codebase`
14. `get_staged_git_changes`
15. `commit_staged_git_changes`

### Step 3.2: Build the `OpenRouterChatSession` Adapter Class
Create a class in `agent/llm.py` that mimics Gemini's `chats.create` return object.

#### Key APIs to Implement:
- `__init__(self, model_name, is_coach=False)`:
  - Initializes the standard OpenAI client targeting `https://openrouter.ai/api/v1`.
  - Builds the standard Raven system prompt (incorporating `global_memory`, `project_name`, `project_memory`, `repo_map`, and `coach_prompt`).
  - Sets up the message history list (`self.messages`).
- `send_message_stream(self, user_input)`:
  - Intercepts input. If input is a list of Gemini-style `types.Part.from_function_response` objects, parse their execution results and map them to standard OpenAI tool messages (`{"role": "tool", "tool_call_id": ..., "content": ...}`).
  - Calls `client.chat.completions.create(..., stream=True, tools=tools)`.
  - Iterates over the stream:
    - Yields text chunks as they arrive.
    - Aggregates delta tool calls.
  - At the end of stream, saves the assistant's message (and any tool calls requested) to `self.messages`.
  - Yields an aggregated `OpenRouterChunk` containing the function calls so `main.py` can invoke them.

### Step 3.3: Update `get_chat_session` & `get_response`
In `agent/llm.py`:
- Update `get_chat_session(is_coach=False)` to check if the active model starts with `gemini-`. If not, return `OpenRouterChatSession(model, is_coach)`.
- Update `get_response(query)` to support OpenRouter completions if the model is not a Gemini model.

### Step 3.4: Expand the Model Selector in `agent/main.py`
In `agent/main.py`:
- Update the `model` command's `choices` menu to offer popular OpenRouter options (e.g., `anthropic/claude-3.5-sonnet`, `deepseek/deepseek-chat`, `openai/gpt-4o`, `meta-llama/llama-3.3-70b-instruct`) alongside the core Gemini models.

---

## 4. Verification and Testing Plan

1. **Verify Dependency Bootstrapping:**
   Run `pip install -e .` to ensure the updated `pyproject.toml` is satisfied and `openai` is loaded.
2. **Verify Offline Imports:**
   Run `python -c "import openai; print(openai.__version__)"` to confirm setup.
3. **Verify OpenRouter Chat Loop:**
   - Configure a mock or active OpenRouter model via `reva model` (e.g. choose `anthropic/claude-3.5-sonnet` or similar).
   - Enter `reva chat` to verify system prompt formatting and streaming.
4. **Verify Tool Call Interception:**
   - Ask the model to fetch current time, read a file, or create a simple file to verify tool schema parsing, user confirmation prompt, execution, and feedback transmission.
