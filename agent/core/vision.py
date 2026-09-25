"""
Vision capabilities and Vision Bridge fallback helper for multimodal processing.
"""

from typing import Dict, Any
from agent.core.settings import settings

VISION_MODEL_KEYWORDS = [
    "gemini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4-vision",
    "claude-3",
    "claude-3-5",
    "claude-3.5",
    "pixtral",
    "qwen-vl",
    "qwen2-vl",
    "llava",
    "vision",
    "multimodal",
]

TEXT_ONLY_EXCLUSION_KEYWORDS = [
    "deepseek-coder",
    "cohere",
    "nemotron",
    "llama-3-8b",
    "llama-3.1-8b",
    "llama-3.2-1b",
    "llama-3.2-3b",
    "mistral-7b",
    "text-only",
]

DEFAULT_FALLBACK_VISION_MODEL = "google/gemini-2.5-flash"


def is_model_vision_capable(model_name: str) -> bool:
    """
    Determines if an AI model supports multimodal image/vision inputs based on model naming conventions.
    """
    if not model_name:
        return False
    lower = model_name.lower().strip()

    # If it explicitly has vision or vl in name, it's vision-capable
    if "vision" in lower or "-vl" in lower or "vl-" in lower:
        return True

    # Check text-only exclusions
    for exc in TEXT_ONLY_EXCLUSION_KEYWORDS:
        if exc in lower:
            return False

    return any(keyword in lower for keyword in VISION_MODEL_KEYWORDS)


def transcribe_image_with_vision_model(
    image_data_uri: str,
    query: str = "",
    vision_model: str = None
) -> Dict[str, Any]:
    """
    Transcribes visual content (text, error traces, code, UI layout, diagrams)
    from an image using a lightweight vision model so that a text-only model can process it.
    """
    from agent.core.llm import get_genai_client

    target_model = vision_model or getattr(settings, "RAVEN_VISION_MODEL", None) or DEFAULT_FALLBACK_VISION_MODEL

    system_instruction = (
        "You are an expert technical vision assistant. "
        "Examine the provided image and extract all relevant information for a software developer.\n\n"
        "Please provide:\n"
        "1. **Visible Text & Code**: Transcribe any visible error messages, stack traces, code snippets, or console logs verbatim.\n"
        "2. **Visual Layout & Components**: Describe UI components, layout structures, diagrams, charts, or architecture flowcharts.\n"
        "3. **Key Observations**: Highlight any values, status codes, URLs, or specific identifiers visible.\n\n"
        "Be concise, precise, and objective so a text-only AI agent can understand the image."
    )

    if query:
        system_instruction += f"\n\nFocus specifically on answering or providing context for this user query: {query}"

    try:
        client = get_genai_client()
        response = client.chat.completions.create(
            model=target_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_instruction},
                        {"type": "image_url", "image_url": {"url": image_data_uri}}
                    ]
                }
            ],
            stream=False,
        )

        content = response.choices[0].message.content or ""
        
        # Record usage for Vision Bridge transcription
        try:
            from agent.core.usage_tracker import UsageTracker
            from agent.core.token_counter import count_tokens
            p_tokens = getattr(getattr(response, "usage", None), "prompt_tokens", None)
            c_tokens = getattr(getattr(response, "usage", None), "completion_tokens", None)
            if p_tokens is None:
                p_tokens = count_tokens(system_instruction, target_model) + 800  # estimated image tokens
            if c_tokens is None:
                c_tokens = count_tokens(content, target_model)
            UsageTracker().record_turn(p_tokens, c_tokens, target_model)
        except Exception:
            pass

        return {
            "success": True,
            "transcription": content,
            "model_used": target_model
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Vision Bridge transcription failed: {e}",
            "model_used": target_model
        }
