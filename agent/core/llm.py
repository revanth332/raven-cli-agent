from dotenv import load_dotenv
import logging
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional, Any, Dict

from openai import OpenAI
from google.auth import default
import google.auth.transport.requests

# Suppress the automatic function calling warning from google-genai
logging.getLogger("google_genai").setLevel(logging.ERROR)


def extract_error_code(e: Exception) -> str:
    """
    Extracts normalized HTTP status or error classification string from API exceptions.
    Matches spec codes: '429', '500', '503', 'TIMEOUT', 'CONTEXT_EXCEEDED', 'AUTH_ERROR'.
    """
    status_code = getattr(e, "status_code", None)
    if status_code is None:
        response = getattr(e, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)

    msg = str(e).lower()
    type_name = type(e).__name__

    # 1. Context window exceeded
    if "context" in msg and ("length" in msg or "exceed" in msg or "too long" in msg or "maximum" in msg or "token" in msg):
        return "CONTEXT_EXCEEDED"
    if "context_length_exceeded" in msg or "context_window" in msg:
        return "CONTEXT_EXCEEDED"

    # 2. Rate limiting
    if status_code == 429 or "ratelimit" in type_name.lower() or "429" in msg or "rate limit" in msg or "quota" in msg:
        return "429"

    # 3. Timeout
    if "timeout" in type_name.lower() or "timeout" in msg or "timed out" in msg:
        return "TIMEOUT"

    # 4. Auth or permissions
    if status_code in (401, 403) or "auth" in type_name.lower() or "permission" in type_name.lower() or "401" in msg or "403" in msg or "unauthorized" in msg:
        return "AUTH_ERROR"

    # 5. Server errors
    if status_code == 503 or "503" in msg or "service unavailable" in msg:
        return "503"
    if status_code == 500 or "500" in msg or "internal server" in msg:
        return "500"
    if status_code and 500 <= status_code < 600:
        return str(status_code)

    # 6. Any other explicit status code
    if status_code:
        return str(status_code)

    # 7. Connection issues
    if "connection" in type_name.lower() or "connection" in msg:
        return "503"

    return type_name if type_name else "UNKNOWN"

from agent.utils import get_active_project_name,get_repo_map,read_prompt_from_file
from agent.tools.memory_tools import get_memory_content,get_project_memory_info
from agent.core.skills_manager import build_skills_prompt_section
from agent.tools.tool_registry import raven_tools
from agent.core.settings import settings
from agent.core.token_counter import count_tokens
from agent.core.usage_tracker import UsageTracker
from agent.core.session_manager import (
    create_session, save_session, load_session, get_active_session_id, set_active_session_id
)
from agent.core.compaction import (
    should_compact_content,
    compact_content,
    save_compacted_memory,
    prune_message_payload,
    should_auto_compact,
)
from agent.utils import use_vertex_ai
load_dotenv()

_genai_client = None
_vertex_credentials = None
_vertex_credentials_lock = Lock()
_vertex_request = google.auth.transport.requests.Request()

def _vertex_token_needs_refresh(credentials):
    if not credentials.token:
        return True

    expiry = getattr(credentials, "expiry", None)
    if expiry is None:
        return True

    if expiry.tzinfo is None:
        now = datetime.utcnow()
    else:
        now = datetime.now(timezone.utc)

    return expiry <= now + timedelta(minutes=5)


def _get_vertex_access_token():
    global _vertex_credentials

    with _vertex_credentials_lock:
        if _vertex_credentials is None:
            _vertex_credentials,_ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

        if _vertex_token_needs_refresh(_vertex_credentials):
            _vertex_credentials.refresh(_vertex_request)

        return _vertex_credentials.token


class AgentChatSession:
    def __init__(self, model_name, session_id=None, is_coach=False):
        self.model_name = model_name

        global_memory = get_memory_content()

        project_memory_path,project_memory = get_project_memory_info()
        if should_compact_content(project_memory):
            compaction_response = compact_content(project_memory)
            if compaction_response["success"]:
                project_memory = compaction_response["content"]
                save_compacted_memory(project_memory_path,project_memory)

        project_name = get_active_project_name()
        repo_map = get_repo_map()
        COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.md") if is_coach else ""

        skills_section = build_skills_prompt_section()

        self.system_prompt = read_prompt_from_file('prompts/system_prompt.md').replace("{global_memory}", global_memory).replace("{project_name}", project_name).replace("{project_memory_path}",project_memory_path).replace("{project_memory}", project_memory).replace("{repo_map}", repo_map).replace("{coach_prompt}", COACH_PROMPT).replace("{skills}", skills_section)
        
        session_data = load_session(session_id) if session_id else None
        target_id = session_id or get_active_session_id()
        if not session_data and target_id:
            session_data = load_session(target_id)

        if not session_data:
            session_data = create_session(model_name=self.model_name, session_id=target_id)

        self.session_id = session_data["session_id"]
        self.session_title = session_data.get("title", "New Conversation")
        self._needs_ai_title = (self.session_title == "New Conversation")
        set_active_session_id(self.session_id)

        # Re-construct message chain: system prompt + persisted user/assistant messages
        restored_messages = [m for m in session_data.get("messages", []) if m.get("role") != "system"]
        self.messages = [{"role": "system", "content": self.system_prompt}] + restored_messages

        self.tracker = UsageTracker()
        self._last_duration_ms = 0.0
        self._last_ttft_ms = None
        self.get_context_usage()

    def save_session_state(self):
        # Exclude system prompt from persisted messages payload for clean state
        non_system_msgs = [m for m in self.messages if m.get("role") != "system"]
        if not non_system_msgs:
            return
        save_session({
            "session_id": self.session_id,
            "title": self.session_title,
            "model_name": self.model_name,
            "messages": non_system_msgs
        })

    def get_context_usage(self):
        context_tokens = count_tokens(self.messages, self.model_name)
        self.tracker.update_context(context_tokens, self.model_name)
        return self.tracker.get_summary(self.model_name)

    def compact_history(self, custom_instructions: str = "") -> dict:
        """
        Compacts past conversation history using LLM distillation (Option B sliding window).
        Saves updated state and returns compaction statistics.
        """
        from agent.core.compaction import compact_conversation_history

        tokens_before = count_tokens(self.messages, self.model_name)
        result = compact_conversation_history(
            self.messages,
            custom_instructions=custom_instructions,
            model_name=self.model_name
        )

        if not result["success"]:
            return result

        self.messages = result["compacted_messages"]
        self.save_session_state()
        tokens_after = count_tokens(self.messages, self.model_name)

        savings = max(0, tokens_before - tokens_after)
        percent = round((savings / tokens_before) * 100, 1) if tokens_before > 0 else 0.0

        result["tokens_before"] = tokens_before
        result["tokens_after"] = tokens_after
        result["savings"] = savings
        result["percent"] = percent

        self.get_context_usage()
        return result

    def record_turn_usage(self, prompt_tokens=None, completion_tokens=None, assistant_response=None, duration_ms=None, ttft_ms=None):
        if prompt_tokens is None:
            prompt_tokens = count_tokens(self.messages, self.model_name)
        if completion_tokens is None and assistant_response is not None:
            completion_tokens = count_tokens(assistant_response, self.model_name)
        completion_tokens = completion_tokens or 0
        if duration_ms is None:
            duration_ms = getattr(self, "_last_duration_ms", 0.0)
        if ttft_ms is None:
            ttft_ms = getattr(self, "_last_ttft_ms", None)
        summary = self.tracker.record_turn(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_name=self.model_name,
            duration_ms=duration_ms,
            ttft_ms=ttft_ms,
            status="success"
        )
        self.get_context_usage()
        self.save_session_state()
        return summary

    @staticmethod
    def _sanitize_message_for_api(msg: dict) -> dict:
        """Strips internal tracking metadata (like model_name) before passing to provider API."""
        clean = {"role": msg["role"]}
        if "content" in msg and msg["content"] is not None:
            clean["content"] = msg["content"]
        if "tool_calls" in msg and msg["tool_calls"] is not None:
            clean["tool_calls"] = msg["tool_calls"]
        if "tool_call_id" in msg and msg["tool_call_id"] is not None:
            clean["tool_call_id"] = msg["tool_call_id"]
        if "name" in msg and msg["name"] is not None:
            clean["name"] = msg["name"]
        return clean

    def _wrap_stream(self, response, start_time: float):
        """
        Wraps LLM response stream to capture time-to-first-token (TTFT)
        and total stream duration, recording errors if stream breaks.
        """
        ttft_recorded = False
        ttft_ms = None
        try:
            for chunk in response:
                if not ttft_recorded:
                    ttft_ms = (time.perf_counter() - start_time) * 1000.0
                    ttft_recorded = True
                yield chunk
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._last_duration_ms = total_duration_ms
            self._last_ttft_ms = ttft_ms
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            error_code = extract_error_code(e)
            try:
                self.tracker.record_turn(
                    prompt_tokens=0,
                    completion_tokens=0,
                    model_name=self.model_name,
                    duration_ms=duration_ms,
                    ttft_ms=ttft_ms,
                    status="error",
                    error_code=error_code
                )
            except Exception:
                pass
            raise e

    def send_message_stream(self, query, execution_instruction=None, allow_tools=True):
        """Send chat history with optional transient loop-control instructions, applying micro-compaction and auto-compaction guardrails."""
        # 1. Autonomous compaction threshold check
        if getattr(settings, "RAVEN_AUTO_COMPACTION_ENABLED", True):
            threshold = getattr(settings, "RAVEN_AUTO_COMPACTION_TOKEN_THRESHOLD", 60000)
            current_tokens = count_tokens(self.messages, self.model_name)
            if should_auto_compact(current_tokens, threshold=threshold, message_count=len(self.messages)):
                try:
                    self.compact_history()
                except Exception as e:
                    logging.getLogger("raven.llm").warning(f"Autonomous compaction trigger failed: {e}")

        # 2. Apply micro-compaction (payload pruning of older tool returns)
        if getattr(settings, "RAVEN_CONTEXT_PRUNING_ENABLED", True):
            retention_turns = getattr(settings, "RAVEN_TOOL_OUTPUT_RETENTION_TURNS", 2)
            stub_threshold = getattr(settings, "RAVEN_TOOL_OUTPUT_STUB_THRESHOLD", 150)
            messages_to_send = prune_message_payload(
                self.messages,
                retention_turns=retention_turns,
                stub_char_threshold=stub_threshold
            )
        else:
            messages_to_send = self.messages

        request_messages = [self._sanitize_message_for_api(m) for m in messages_to_send]
        if query is not None:
            request_messages.append(self._sanitize_message_for_api(self._create_message("user", content=query)))
        if execution_instruction:
            request_messages.append(self._sanitize_message_for_api(self._create_message("system", content=execution_instruction)))

        request_args = {
            "model": self.model_name,
            "messages": request_messages,
            "stream": True,
        }
        if allow_tools:
            request_args["tools"] = raven_tools

        start_time = time.perf_counter()
        try:
            response = get_genai_client().chat.completions.create(**request_args)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            error_code = extract_error_code(e)
            try:
                self.tracker.record_turn(
                    prompt_tokens=0,
                    completion_tokens=0,
                    model_name=self.model_name,
                    duration_ms=duration_ms,
                    ttft_ms=None,
                    status="error",
                    error_code=error_code
                )
            except Exception:
                pass
            raise e

        return self._wrap_stream(response, start_time)

    def commit_user_message(self, content):
        if content is not None:
            if self.session_title == "New Conversation":
                title_source = ""
                if isinstance(content, str) and content.strip():
                    title_source = content.strip()
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            title_source = item.get("text", "").strip()
                            if title_source:
                                break
                    if not title_source:
                        title_source = "Image Query"

                if title_source:
                    clean_title = title_source.replace("\n", " ")
                    self.session_title = clean_title[:32] + ("..." if len(clean_title) > 32 else "")
                    try:
                        from agent.utils import set_terminal_title
                        set_terminal_title(f"Raven - {self.session_title}")
                    except Exception:
                        pass
                self._needs_ai_title = True

            self.messages.append(self._create_message("user", content=content))
            self.save_session_state()

    def update_session_title(self, new_title: str) -> None:
        """Updates the session title in memory and persists to disk."""
        if new_title and new_title.strip():
            self.session_title = new_title.strip()
            self._needs_ai_title = False
            self.save_session_state()
            try:
                from agent.utils import set_terminal_title
                set_terminal_title(f"Raven - {self.session_title}")
            except Exception:
                pass

    def commit_assistant_message(self,content=None,tool_calls=None):
        if content is not None or tool_calls is not None:
            self.messages.append(self._create_message("assistant",content=content,tool_calls=tool_calls))
            self.save_session_state()

    def add_message(self,role,content=None,tool_call_id=None,name=None,tool_calls=None):
        """Helper to append structured assistant or tool returns to history"""
        msg = self._create_message(role,content=content,tool_call_id=tool_call_id,name=name,tool_calls=tool_calls)
        self.messages.append(msg)

    def _create_message(self, role, content=None, tool_call_id=None, name=None, tool_calls=None, model_name=None):
        msg = {"role": role}
        if content is not None:
            msg["content"] = content
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        if name is not None:
            msg["name"] = name
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        if role == "assistant":
            msg["model_name"] = model_name or self.model_name
        return msg


def reset_genai_client():
    """Invalidates the cached OpenAI client instance to force re-instantiation with new settings."""
    global _genai_client, _vertex_credentials
    _genai_client = None
    _vertex_credentials = None


def get_genai_client():
    global _genai_client

    base_url = settings.RAVEN_BASE_URL
    if use_vertex_ai():
        api_key = _get_vertex_access_token()
        if not base_url:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1"
            if not project_id:
                try:
                    _, project_id = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                except Exception:
                    pass
            if project_id:
                base_url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/endpoints/openapi"

        if not api_key or not base_url:
            raise ValueError("Credentials are missing!!! Please use 'config' command to configure the credentials.")

        return OpenAI(
            base_url=base_url,
            api_key=api_key
        )

    if not _genai_client:
        api_key = settings.RAVEN_API_KEY or "ollama"

        if not base_url:
            raise ValueError("Credentials are missing!!! Please use 'config' command to configure the credentials.")
        _genai_client = OpenAI(
            base_url=base_url,
            api_key=api_key

        )
    return _genai_client


def get_chat_session(session_id=None, is_coach=False):
    """Initializes and returns an interactive chat object."""
    return AgentChatSession(settings.RAVEN_MODEL, session_id=session_id, is_coach=is_coach)


def generate_ai_session_title(user_query, assistant_response=None, fallback_model=None) -> str:
    """
    Generates a concise 3-5 word title summarizing the user query using the configured
    SMALL_MODEL (settings.RAVEN_SMALL_MODEL) with fallback to the active selected model.
    """
    primary_model = getattr(settings, "RAVEN_SMALL_MODEL", None) or getattr(settings, "SMALL_MODEL", None)
    active_fallback = fallback_model or getattr(settings, "RAVEN_MODEL", None) or getattr(settings, "MODEL", None)

    models_to_try = []
    if primary_model:
        models_to_try.append(primary_model)
    if active_fallback and active_fallback not in models_to_try:
        models_to_try.append(active_fallback)

    query_text = user_query
    if isinstance(user_query, list):
        for item in user_query:
            if isinstance(item, dict) and item.get("type") == "text":
                query_text = item.get("text", "")
                break
        if not isinstance(query_text, str):
            query_text = "Image analysis"

    prompt = (
        "Generate a concise, descriptive title of 3 to 5 words summarizing the user's intent or topic.\n"
        "Strict rules:\n"
        "- Do NOT use quotes, quotation marks, punctuation, or backticks.\n"
        "- Output ONLY the title text, nothing else.\n"
        "- Title Case (e.g., 'Docker Container Setup', 'React State Optimization').\n\n"
        f"User Prompt:\n{str(query_text)[:500]}"
    )
    if assistant_response:
        prompt += f"\n\nAssistant Snippet:\n{str(assistant_response)[:300]}"

    client = get_genai_client()
    for model_name in models_to_try:
        t_start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                stream=False
            )
            title_dur_ms = (time.perf_counter() - t_start) * 1000.0
            raw_title = resp.choices[0].message.content or ""
            clean_title = raw_title.strip().strip('"').strip("'").strip("`").replace("\n", " ").strip()
            clean_title = clean_title.rstrip(".")

            # Record usage for title generation call
            try:
                from agent.core.usage_tracker import UsageTracker
                from agent.core.token_counter import count_tokens
                p_tokens = getattr(getattr(resp, "usage", None), "prompt_tokens", None)
                c_tokens = getattr(getattr(resp, "usage", None), "completion_tokens", None)
                if p_tokens is None:
                    p_tokens = count_tokens(prompt, model_name)
                if c_tokens is None:
                    c_tokens = count_tokens(clean_title, model_name)
                UsageTracker().record_turn(
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    model_name=model_name,
                    duration_ms=title_dur_ms,
                    status="success"
                )
            except Exception:
                pass

            if clean_title:
                return clean_title[:40].strip()
        except Exception as e:
            title_dur_ms = (time.perf_counter() - t_start) * 1000.0
            try:
                from agent.core.usage_tracker import UsageTracker
                UsageTracker().record_turn(
                    prompt_tokens=0,
                    completion_tokens=0,
                    model_name=model_name,
                    duration_ms=title_dur_ms,
                    status="error",
                    error_code=extract_error_code(e)
                )
            except Exception:
                pass
            continue

    fallback_title = str(query_text).strip().replace("\n", " ")
    return fallback_title[:32] + ("..." if len(fallback_title) > 32 else "")

