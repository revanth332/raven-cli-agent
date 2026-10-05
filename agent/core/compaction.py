import os
import tempfile
import logging
from agent.core.token_counter import count_tokens
from agent.utils import read_prompt_from_file

logger = logging.getLogger("raven.compaction")

def should_compact_content(content: str, token_limit: int = 1200) -> bool:
    """
    Verifies and returns a boolean stating whether compaction is required or not.
    """
    token_count = count_tokens(content)
    print(token_count)
    return token_count > token_limit

def compact_content(content: str) -> dict:
    """
    Attempts to compact the given memory context using LLM distillation.
    Returns a dictionary of success status and content.
    """
    if not content:
        return {"success": True, "content": ""}

    # Break circular import of get_genai_client by importing it inside the function scope
    from agent.core.llm import get_genai_client
    from agent.core.settings import settings

    try:
        prompt = read_prompt_from_file("prompts/compaction_prompt.md")
    except Exception as e:
        logger.error(f"Failed to read compaction prompt file: {e}")
        return {"success": False, "content": content}

    # Use SMALL_MODEL with fallback to main model
    primary_model = getattr(settings, "RAVEN_SMALL_MODEL", None) or getattr(settings, "SMALL_MODEL", None)
    fallback_model = getattr(settings, "RAVEN_MODEL", None) or getattr(settings, "MODEL", None)
    models_to_try = []
    if primary_model:
        models_to_try.append(primary_model)
    if fallback_model and fallback_model not in models_to_try:
        models_to_try.append(fallback_model)

    if not models_to_try:
        logger.error("No model configured for compaction")
        return {"success": False, "content": content}

    max_retries = 3
    tried = 1
    while tried <= max_retries:
        for model in models_to_try:
            try:
                response = get_genai_client().chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Memory:\n {content}"}
                    ],
                    stream=False,
                )
                compacted_content = response.choices[0].message.content
                if not compacted_content:
                    tried += 1
                    continue

                token_count_original = count_tokens(content)
                token_count_compacted = count_tokens(compacted_content)

                if token_count_original < token_count_compacted:
                    logger.warning(
                        f"Compaction attempt {tried} produced larger text "
                        f"({token_count_compacted} tokens) than original ({token_count_original} tokens). Retrying..."
                    )
                    tried += 1
                else:
                    return {"success": True, "content": compacted_content}
            except Exception as error:
                error_str = str(error)
                logger.warning(f"Compaction attempt {tried} failed: {error_str}")
                if "429" in error_str or "exhausted" in error_str or "quota" in error_str:
                    tried += 1
                else:
                    return {"success": False, "content": content}

    return {"success": False, "content": content}

def save_compacted_memory(file_path: str, compacted_content: str) -> bool:
    """
    Safely and atomically overwrites the project memory file to prevent corruption/data loss.
    """
    if not file_path or not compacted_content:
        return False
    directory = os.path.dirname(file_path)
    try:
        # Write to temporary file first to guarantee atomic write via os.replace
        with tempfile.NamedTemporaryFile('w', dir=directory, delete=False, encoding='utf-8') as tf:
            tf.write(compacted_content)
            temp_name = tf.name
        
        os.replace(temp_name, file_path)
        return True
    except Exception as e:
        if 'temp_name' in locals() and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except Exception:
                pass
        logger.error(f"Error writing compacted memory atomically: {e}")
        return False


def format_messages_for_compaction(messages: list[dict], max_tool_chars: int = 1000) -> str:
    """Formats a list of message dicts into a clean text transcript for distillation."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls")
        name = msg.get("name")

        if role == "USER":
            lines.append(f"USER:\n{content}\n")
        elif role == "ASSISTANT":
            if content:
                lines.append(f"ASSISTANT:\n{content}\n")
            if tool_calls:
                call_strs = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args = fn.get("arguments", "")
                    call_strs.append(f"{fn_name}({fn_args})")
                lines.append("ASSISTANT TOOL CALLS:\n" + "\n".join(call_strs) + "\n")
        elif role == "TOOL":
            display_content = str(content)
            if len(display_content) > max_tool_chars:
                display_content = display_content[:max_tool_chars] + f"... [truncated {len(display_content) - max_tool_chars} chars]"
            lines.append(f"TOOL RESULT ({name or 'tool'}):\n{display_content}\n")
        else:
            if content:
                lines.append(f"{role}:\n{content}\n")
    return "\n".join(lines)


def should_auto_compact(current_tokens: int, threshold: int = 60000, message_count: int = 0) -> bool:
    """
    Determines if conversation context exceeds the token ceiling for auto-compaction.
    Requires at least 6 messages to ensure there is meaningful multi-turn history to distill.
    """
    if message_count > 0 and message_count < 6:
        return False
    return current_tokens >= threshold


def prune_message_payload(
    messages: list[dict],
    retention_turns: int = 2,
    stub_char_threshold: int = 150,
    strip_images: bool = True
) -> list[dict]:
    """
    Performs micro-compaction on an outbound message list without mutating the original list.
    Preserves raw tool outputs and multimodal payloads for the most recent `retention_turns` user turns.
    For turns older than the retention horizon:
      - Bulky tool outputs (> stub_char_threshold chars) are replaced with concise summary stubs.
      - Exact role, tool_call_id, and tool name are preserved to maintain LLM API pairing invariants.
      - Base64 image payloads in older user turns are replaced with text placeholders.
    """
    if not messages:
        return []

    # Identify user turn indices by scanning messages
    user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    total_user_turns = len(user_indices)

    # Determine cutoff index: messages before this index are considered outside the retention horizon
    if total_user_turns <= retention_turns:
        cutoff_idx = 0
    else:
        cutoff_idx = user_indices[total_user_turns - retention_turns]

    pruned = []
    for idx, msg in enumerate(messages):
        msg_copy = dict(msg)
        is_historical = (idx < cutoff_idx)

        role = msg_copy.get("role")
        if is_historical:
            if role == "tool":
                content = msg_copy.get("content", "")
                tool_name = msg_copy.get("name", "tool")
                content_str = str(content) if content is not None else ""
                
                # If content is already a stub or sufficiently short, leave as is
                if len(content_str) > stub_char_threshold and not content_str.startswith("[Output of "):
                    line_count = len(content_str.splitlines())
                    char_count = len(content_str)
                    stub = f"[Output of {tool_name} omitted: {line_count:,} lines ({char_count:,} chars). Result previously processed in prior turn.]"
                    msg_copy["content"] = stub
            elif role == "user" and strip_images:
                user_content = msg_copy.get("content")
                if isinstance(user_content, list):
                    cleaned_content = []
                    for item in user_content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            cleaned_content.append({"type": "text", "text": "[Image attachment previously processed in prior turn]"})
                        else:
                            cleaned_content.append(item)
                    msg_copy["content"] = cleaned_content

        pruned.append(msg_copy)

    return pruned


def compact_conversation_history(messages: list[dict], custom_instructions: str = "", model_name: str = None) -> dict:
    """
    Distills earlier conversation messages into a structured summary using LLM.
    Summarizes all prior turns while preserving the entire final user turn.
    
    Returns:
        {
            "success": bool,
            "summary": str,
            "compacted_messages": list[dict],
            "error": str or None
        }
    """
    if not messages:
        return {"success": False, "summary": "", "compacted_messages": messages, "error": "No messages to compact."}

    system_msg = messages[0] if messages[0].get("role") == "system" else None
    non_system = [m for m in messages if m.get("role") != "system"]

    user_indices = [i for i, m in enumerate(non_system) if m.get("role") == "user"]
    if len(user_indices) < 2:
        return {
            "success": False,
            "summary": "",
            "compacted_messages": messages,
            "error": "Conversation is too short to compact (requires at least 2 completed user turns)."
        }

    # Slice at the start of the final user turn so tool/assistant sequence pairing is strictly preserved
    last_user_idx = user_indices[-1]
    to_compact = non_system[:last_user_idx]
    preserved = non_system[last_user_idx:]

    transcript = format_messages_for_compaction(to_compact)
    if not transcript.strip():
        return {
            "success": False,
            "summary": "",
            "compacted_messages": messages,
            "error": "No meaningful history to compact."
        }

    from agent.core.llm import get_genai_client
    from agent.core.settings import settings

    try:
        base_prompt = read_prompt_from_file("prompts/session_compaction_prompt.md")
    except Exception as e:
        logger.error(f"Failed to read session compaction prompt: {e}")
        return {"success": False, "summary": "", "compacted_messages": messages, "error": str(e)}

    user_prompt = f"Transcript to Compact:\n\n{transcript}"
    if custom_instructions and custom_instructions.strip():
        user_prompt += f"\n\nADDITIONAL FOCUS INSTRUCTIONS FROM USER:\n{custom_instructions.strip()}"

    # Use SMALL_MODEL with fallback to main model
    primary_model = getattr(settings, "RAVEN_SMALL_MODEL", None) or getattr(settings, "SMALL_MODEL", None)
    fallback_model = model_name or getattr(settings, "RAVEN_MODEL", None) or getattr(settings, "MODEL", None)
    target_model = primary_model or fallback_model

    try:
        response = get_genai_client().chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=False,
        )
        summary = response.choices[0].message.content or ""
        if not summary.strip():
            return {"success": False, "summary": "", "compacted_messages": messages, "error": "Model returned empty summary."}

        synthetic_user = {
            "role": "user",
            "content": f"[Previous Conversation Context & Summary]\n{summary.strip()}"
        }
        synthetic_assistant = {
            "role": "assistant",
            "content": "Understood. I have absorbed the context, decisions, and file changes from our earlier discussion. Let's proceed."
        }

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.extend([synthetic_user, synthetic_assistant])
        new_messages.extend(preserved)

        return {
            "success": True,
            "summary": summary.strip(),
            "compacted_messages": new_messages,
            "error": None
        }
    except Exception as e:
        logger.error(f"Failed to compact conversation history: {e}")
        return {"success": False, "summary": "", "compacted_messages": messages, "error": str(e)}


