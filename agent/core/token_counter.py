"""
Utility for counting tokens in text strings and message payloads.
"""

from typing import Union, List, Dict, Any
import json

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


def count_tokens(text_or_messages: Union[str, List[Dict[str, Any]], Dict[str, Any]], model_name: str = "gpt-4o") -> int:
    """
    Counts tokens for strings, message dicts, or lists of messages.
    Uses tiktoken if available, with heuristic fallback (approx 4 chars per token).
    """
    if not text_or_messages:
        return 0

    if isinstance(text_or_messages, list):
        return sum(count_tokens(m, model_name) for m in text_or_messages)

    if isinstance(text_or_messages, dict):
        # Convert message dictionary to standard format for token estimation
        content = text_or_messages.get("content") or ""
        role = text_or_messages.get("role") or ""
        tool_calls = text_or_messages.get("tool_calls") or ""

        if isinstance(content, list):
            # Multimodal content blocks: separate text and estimate images
            text_parts = []
            image_tokens = 0
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        # Standard fixed estimate per image (~1,000 tokens for Gemini/GPT-4o)
                        image_tokens += 1000
            
            combined_text = " ".join(text_parts)
            serialized = f"{role}: {combined_text}"
            if tool_calls:
                serialized += f" tool_calls: {json.dumps(tool_calls)}"
            return count_tokens(serialized, model_name) + image_tokens + 4
        
        serialized = f"{role}: {content}"
        if tool_calls:
            serialized += f" tool_calls: {json.dumps(tool_calls)}"
            
        return count_tokens(serialized, model_name) + 4  # overhead per message

    # Handle string
    text = str(text_or_messages)
    if not text:
        return 0

    if text.startswith("data:image/"):
        return 1000

    if HAS_TIKTOKEN:
        try:
            encoding_name = "o200k_base" if "gpt-4o" in model_name.lower() or "o1" in model_name.lower() else "cl100k_base"
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception:
            pass

    # Heuristic fallback: standard estimate of ~4 characters per token for English/code text
    return max(1, len(text) // 4)
