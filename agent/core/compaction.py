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

    try:
        prompt = read_prompt_from_file("prompts/compaction_prompt.md")
    except Exception as e:
        logger.error(f"Failed to read compaction prompt file: {e}")
        return {"success": False, "content": content}

    max_retries = 3
    tried = 1
    while tried <= max_retries:
        try:
            response = get_genai_client().chat.completions.create(
                model="google/gemini-2.5-flash",
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

