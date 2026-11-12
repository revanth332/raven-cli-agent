# Technical Specification: Decoupled Image Generation Engine & `/image-model` Flow

## 1. Objective & Problem Statement

Currently, Raven's image generation subsystem (`agent/tools/image_generation_tools.py`) is tightly coupled to the active chat session's provider state (`RAVEN_BASE_URL`, `RAVEN_API_KEY`, `RAVEN_USE_VERTEX_AI`, and `get_genai_client()`). This causes three critical architectural failures:

1. **Provider Lock-in & Endpoint Crashes:**
   When the active chat provider does not offer an `/images/generations` endpoint (e.g., Groq, Anthropic, DeepSeek, or text-only local Ollama), calling `_generate_with_openai_compatible()` reuses `get_genai_client()` from `agent/core/llm.py` and immediately fails.
2. **Global Flag Pollution (`RAVEN_USE_VERTEX_AI`):**
   `_generate_with_google_genai()` relies on `use_vertex_ai()`, which inspects the active chat provider's `RAVEN_USE_VERTEX_AI` flag. If the user is chatting via OpenRouter or Groq (`RAVEN_USE_VERTEX_AI=False`), invoking `gemini-3.1-flash-image` or passing a reference image initializes `google.genai.Client(vertexai=False)` and fails due to missing `GEMINI_API_KEY`, ignoring the user's configured Vertex AI preset.
3. **Non-Deterministic Heuristic Routing:**
   Lines 524–542 in `agent/tools/image_generation_tools.py` silently override `IMAGE_MODEL` to `"gemini-3.1-flash-image"` whenever `use_vertex_ai()` is True or a reference image is passed, and branch using fragile substring checks (`"imagen" in target_model or "gemini" in target_model`).

### Goal
Completely decouple the Image Generation Engine from the active chat LLM provider so the user can:
- Use **any** chat provider (e.g., Groq, OpenRouter, custom OpenAI endpoint) while independently pinning a dedicated **Image Provider Preset** and **Image Model** (e.g., `Google Vertex AI` + `gemini-3.1-flash-image`, or `OpenRouter` + `black-forest-labs/flux-1-schnell`).
- Resolve credentials via `~/.raven/providers.json` preset binding with support for environment and `config.json` overrides.
- Route requests deterministically based on the resolved Image Provider's `provider_type` (`vertex` vs `openai`) with zero silent model hijacking.
- Configure and switch both the **Image Provider Preset** and **Image Model** interactively via a dedicated `/image-model` TUI modal (as well as CLI arguments).

---

## 2. Configuration & Preset Schema Architecture

### 2.1 `~/.raven/providers.json` Schema Extension (`agent/core/preset_manager.py`)

Extend `~/.raven/providers.json` to store the active image preset and per-preset image model lists alongside the existing chat presets:

```json
{
  "active_preset": "OpenRouter",
  "image_preset": "Google Vertex AI",
  "presets": {
    "OpenRouter": {
      "provider_type": "openai",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "sk-or-...",
      "default_model": "google/gemini-2.5-flash",
      "use_vertex_ai": false,
      "models": [
        "google/gemini-2.5-flash",
        "anthropic/claude-3.7-sonnet"
      ],
      "default_image_model": "black-forest-labs/flux-1-schnell",
      "image_models": [
        "black-forest-labs/flux-1-schnell",
        "black-forest-labs/flux-1-dev",
        "openai/gpt-image-1"
      ]
    },
    "Google Vertex AI": {
      "provider_type": "vertex",
      "base_url": "",
      "api_key": "",
      "default_model": "gemini-2.5-pro",
      "use_vertex_ai": true,
      "models": [
        "gemini-2.5-pro",
        "gemini-2.5-flash"
      ],
      "default_image_model": "gemini-3.1-flash-image",
      "image_models": [
        "gemini-3.1-flash-image",
        "gemini-3-pro-image",
        "imagen-3.0-generate-002"
      ]
    }
  }
}
```

#### Backward-Compatible Migration in `PresetManager`
- On `load_providers_data()`, if `"image_preset"` is missing from `providers.json`, default it to `"Google Vertex AI"` (if present in `presets`) or fall back to `"active_preset"`.
- Ensure each preset in `presets` has `"default_image_model"` and `"image_models"` populated with sensible defaults if missing, without overwriting user customizations.

### 2.2 Settings & Environment Override Precedence (`agent/core/settings.py`)

Add explicit image engine configuration keys to `Settings.DEFAULTS` in `agent/core/settings.py`:

| Setting Key | Default | Purpose |
| :--- | :--- | :--- |
| `IMAGE_PROVIDER` | `""` | Name of the preset in `~/.raven/providers.json` used for image generation (e.g., `"Google Vertex AI"`, `"OpenRouter"`). When empty, falls back to `providers.json -> image_preset`. |
| `IMAGE_MODEL` | `"black-forest-labs/flux-1-schnell"` | Default or active image model identifier. |
| `IMAGE_BASE_URL` | `""` | Optional standalone base URL override for custom OpenAI-compatible image endpoints not bound to a preset. |
| `IMAGE_API_KEY` | `""` | Optional standalone API key override for the image engine. |
| `IMAGE_USE_VERTEX_AI` | `None` | Optional boolean override (`True`/`False`). When `None`, inherits from the resolved `IMAGE_PROVIDER` preset's `use_vertex_ai` / `provider_type`. |

#### Resolution Precedence Order (`resolve_image_engine_config()`)
When `generate_image` (or `/imagine`) executes, it calls `resolve_image_engine_config(model_override: Optional[str] = None)` which resolves:

1. **Provider Preset Lookup:**
   - Check `settings.IMAGE_PROVIDER` (from env or `config.json`).
   - If unset, read `image_preset` from `~/.raven/providers.json` via `get_image_preset()`.
   - Load the corresponding preset dictionary (`preset_cfg`) from `providers.json`.
2. **Endpoint & Auth Resolution:**
   - `provider_type`: `"vertex"` if `IMAGE_USE_VERTEX_AI` is explicitly `True` or `preset_cfg.get("provider_type") == "vertex"` or `preset_cfg.get("use_vertex_ai") is True`; otherwise `"openai"`.
   - `base_url`: `settings.IMAGE_BASE_URL` if non-empty, else `preset_cfg.get("base_url", "")`.
   - `api_key`: `settings.IMAGE_API_KEY` if non-empty, else `preset_cfg.get("api_key", "")` (falling back to `os.environ.get("GEMINI_API_KEY")` or `settings.RAVEN_API_KEY` only if the selected preset corresponds to the active env key).
3. **Target Model Resolution:**
   - Explicit `model` parameter passed to `generate_image(model=...)` (if provided).
   - Else `settings.IMAGE_MODEL` (if set in env/`config.json`).
   - Else `preset_cfg.get("default_image_model")`.

---

## 3. Strict, Deterministic Routing (`agent/tools/image_generation_tools.py`)

### 3.1 Removal of Active Chat Coupling & Heuristics
- **Remove** `from agent.core.llm import get_genai_client, use_vertex_ai` from `agent/tools/image_generation_tools.py`.
- **Remove** the silent override that forces `target_model = "gemini-3.1-flash-image"` when `use_vertex_ai()` is True or `reference_image` is present.
- **Remove** substring routing heuristics (`"imagen" in target_model.lower() or "gemini" in target_model.lower()`).

### 3.2 Dedicated Client Instantiation & Routing Rules
Routing is strictly governed by the resolved `ImageEngineConfig`:

1. **Case A: `provider_type == "vertex"` (or Google GenAI backend)**
   - Instantiates an isolated `google.genai.Client`:
     - When `use_vertex_ai=True`: initializes `genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"), location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))`.
     - When `use_vertex_ai=False` (Google AI Studio / Gemini API Key preset): initializes `genai.Client(vertexai=False, api_key=resolved_api_key)`.
   - Supports both text-to-image (`generate_content` / `generate_images` for Imagen models) and multimodal reference-image editing (`contents=[reference_image, full_prompt]`).
2. **Case B: `provider_type == "openai"` (OpenRouter, OpenAI, Together, Custom OpenAI-compatible)**
   - Validates that `resolved_api_key` is present (unless pointing to a local endpoint) and instantiates an isolated `openai.OpenAI(base_url=resolved_base_url, api_key=resolved_api_key)` client.
   - **Reference Image Guard:** If `reference_image` is provided (`use_attached_image=True` or `reference_image_path` is set) and the target OpenAI-compatible endpoint does not support multimodal image input via `/images/generations`, return an immediate, actionable error message:
     `"Error: Reference image editing is not supported by the current OpenAI-compatible image provider ('<preset_name>' / '<target_model>'). Use '/image-model' to switch your Image Provider to 'Google Vertex AI' (e.g., 'gemini-3.1-flash-image')."`
   - Executes `client.images.generate(...)` (with OpenRouter raw HTTP fallback if needed) using `resolved_base_url` and `resolved_api_key`.

---

## 4. Dedicated `/image-model` TUI Modal & CLI Flow

### 4.1 `ImageModelSelectModal` (`agent/terminal_ui/image_model_select_modal.py`)
Create a dedicated, emoji-free modal (`ImageModelSelectModal(ModalScreen[Optional[Dict[str, str]]])`) that allows the user to select both the **Image Provider Preset** and the **Image Model** in a single cohesive view:

- **Layout & Controls:**
  1. **Header Row:** Title `Configure Image Generation Engine` and `esc to close`.
  2. **Provider Selector (`OptionList` or Cycling Header / Section):**
     - Lists available presets from `~/.raven/providers.json` (e.g., `Google Vertex AI`, `OpenRouter`, plus any user-created presets).
     - Marks the currently active `image_preset` with `[ACTIVE]`.
     - Selecting or switching the provider preset immediately updates the model list below to show that provider's `image_models` (plus any cached/discovered image-capable models).
  3. **Search Input (`#image_search_input`):** Filter image models for the selected provider.
  4. **Image Model List (`#image_model_list`):**
     - Displays curated/saved `image_models` for the selected provider preset.
     - Highlights the active `default_image_model` / `IMAGE_MODEL`.
  5. **Custom Image Model Input (`#custom_image_model_input`):**
     - Allows typing any arbitrary model ID (e.g., `black-forest-labs/flux-1.1-pro` or `gemini-3-pro-image`). Submitting saves the custom model to that preset's `image_models` list in `~/.raven/providers.json` and activates it.
  6. **Footer Shortcuts:** `tab switch focus    enter apply    ctrl+d delete custom model    esc cancel`.

### 4.2 `/image-model` Command Behavior (`agent/terminal_ui/app.py` & `slash_commands.py`)
- **Interactive Mode (`/image-model` with no arguments):**
  - Pushes `ImageModelSelectModal` onto the screen instead of printing static help text.
  - On modal dismissal with a selection (`{"preset_name": ..., "model": ...}`):
    - Updates `image_preset` and the preset's `default_image_model` in `~/.raven/providers.json` via `PresetManager`.
    - Persists `IMAGE_PROVIDER` and `IMAGE_MODEL` via `settings.set_config(...)`.
    - Displays a system confirmation card and notification: `Image Engine set to <model> via <preset_name>` (chat provider and chat session remain untouched).
- **Direct CLI Argument Mode (`/image-model <model_name>` or `/image-model <preset_name>:<model_name>`):**
  - Continues to work for fast keyboard-only switching without opening the modal, updating the active image model (and optional preset prefix) immediately.

---

## 5. Module-by-Module Implementation Plan

| File | Action | Description |
| :--- | :--- | :--- |
| `agent/core/preset_manager.py` | Modify | Add `image_preset`, `default_image_model`, and `image_models` support to default presets and schema normalization. Add helper functions: `get_image_preset()`, `set_image_preset(preset_name, model=None)`, `add_preset_image_model(preset_name, model_id)`, and `remove_preset_image_model(preset_name, model_id)`. |
| `agent/core/settings.py` | Modify | Add `IMAGE_PROVIDER`, `IMAGE_BASE_URL`, `IMAGE_API_KEY`, and `IMAGE_USE_VERTEX_AI` to `Settings.DEFAULTS` with proper boolean/string coercion. |
| `agent/tools/image_generation_tools.py` | Modify | Add `resolve_image_engine_config()`. Decouple `_generate_with_openai_compatible()` and `_generate_with_google_genai()` from `agent.core.llm`. Remove silent model overrides and substring heuristics; enforce strict provider-based routing and clear reference-image validation errors. |
| `agent/terminal_ui/image_model_select_modal.py` | Create | Implement `ImageModelSelectModal` allowing independent selection of Image Provider Preset and Image Model with custom model entry and persistence. |
| `agent/terminal_ui/styles/image_model_select_modal.tcss` | Create | Style `ImageModelSelectModal` matching Raven's `#1e1e1e` dark aesthetic and emerald green (`#10b981`) accents, strictly emoji-free. |
| `agent/terminal_ui/app.py` | Modify | Wire `/image-model` (without args) to open `ImageModelSelectModal`, and support `/image-model <model>` direct updates synced with `PresetManager`. |
| `agent/terminal_ui/slash_commands.py` | Modify | Update `/image-model` description to reflect interactive provider + model selection. |
