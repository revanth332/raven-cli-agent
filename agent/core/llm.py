from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock

from openai import OpenAI
from google.auth import default
import google.auth.transport.requests

# Suppress the automatic function calling warning from google-genai
logging.getLogger("google_genai").setLevel(logging.ERROR)

from agent.utils import get_active_project_name,get_repo_map,read_prompt_from_file
from agent.tools.memory_tools import get_memory_content,get_project_memory
from agent.tools.tool_registry import raven_tools
from agent.core.settings import settings
from agent.core.token_counter import count_tokens
from agent.core.usage_tracker import UsageTracker
from agent.core.session_manager import (
    create_session, save_session, load_session, get_active_session_id, set_active_session_id
)

load_dotenv()

_genai_client = None
_vertex_credentials = None
_vertex_credentials_lock = Lock()
_vertex_request = google.auth.transport.requests.Request()


def _use_vertex_ai():
    return str(settings.RAVEN_USE_VERTEX_AI).strip().lower() == "true"


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
        project_memory = get_project_memory()
        project_name = get_active_project_name()
        repo_map = get_repo_map()
        COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.md") if is_coach else ""

        self.system_prompt = read_prompt_from_file('prompts/system_prompt.md').replace("{global_memory}", global_memory).replace("{project_name}", project_name).replace("{project_memory}", project_memory).replace("{repo_map}", repo_map).replace("{coach_prompt}", COACH_PROMPT)
        
        session_data = load_session(session_id) if session_id else None
        if not session_data:
            target_id = session_id or get_active_session_id()
            session_data = load_session(target_id) if target_id else None

        if not session_data:
            session_data = create_session(model_name=self.model_name)

        self.session_id = session_data["session_id"]
        self.session_title = session_data.get("title", "New Conversation")
        set_active_session_id(self.session_id)

        # Re-construct message chain: system prompt + persisted user/assistant messages
        restored_messages = [m for m in session_data.get("messages", []) if m.get("role") != "system"]
        self.messages = [{"role": "system", "content": self.system_prompt}] + restored_messages

        self.tracker = UsageTracker()
        self.get_context_usage()

    def save_session_state(self):
        # Exclude system prompt from persisted messages payload for clean state
        non_system_msgs = [m for m in self.messages if m.get("role") != "system"]
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

    def record_turn_usage(self, prompt_tokens=None, completion_tokens=None, assistant_response=None):
        if prompt_tokens is None:
            prompt_tokens = count_tokens(self.messages, self.model_name)
        if completion_tokens is None and assistant_response is not None:
            completion_tokens = count_tokens(assistant_response, self.model_name)
        completion_tokens = completion_tokens or 0
        summary = self.tracker.record_turn(prompt_tokens, completion_tokens, self.model_name)
        self.get_context_usage()
        self.save_session_state()
        return summary

    def send_message_stream(self,query):
        """
        Sends the current chat history stream. 
        If a query is passed, it appends it as a new user message first.
        If query is None, it continues the loop (e.g., passing back tool outputs).
        """
        request_messages = self.messages
        if query is not None:
            request_messages = self.messages + [self._create_message("user",content=query)]
        response = get_genai_client().chat.completions.create(
            model=self.model_name,
            messages=request_messages,
            tools=raven_tools,
            stream=True,
        )

        return response

    def commit_user_message(self,content):
        if content is not None:
            if self.session_title == "New Conversation" and isinstance(content, str) and content.strip():
                clean_title = content.strip().replace("\n", " ")
                self.session_title = clean_title[:32] + ("..." if len(clean_title) > 32 else "")
            self.messages.append(self._create_message("user",content=content))
            self.save_session_state()

    def commit_assistant_message(self,content=None,tool_calls=None):
        if content is not None or tool_calls is not None:
            self.messages.append(self._create_message("assistant",content=content,tool_calls=tool_calls))
            self.save_session_state()

    def add_message(self,role,content=None,tool_call_id=None,name=None,tool_calls=None):
        """Helper to append structured assistant or tool returns to history"""
        msg = self._create_message(role,content=content,tool_call_id=tool_call_id,name=name,tool_calls=tool_calls)
        self.messages.append(msg)

    def _create_message(self,role,content=None,tool_call_id=None,name=None,tool_calls=None):
        msg = {"role":role}
        if content is not None:
            msg["content"] = content
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        if name is not None:
            msg["name"] = name
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        return msg


def get_genai_client():
    global _genai_client

    base_url = settings.RAVEN_BASE_URL
    if _use_vertex_ai():
        api_key = _get_vertex_access_token()

        if not api_key or not base_url:
            raise ValueError("Credentials are missing!!! Please use 'config' command to configure the credentials.")

        return OpenAI(
            base_url=base_url,
            api_key=api_key
        )

    if not _genai_client:
        api_key = settings.RAVEN_API_KEY

        if not api_key or not base_url:
            raise ValueError("Credentials are missing!!! Please use 'config' command to configure the credentials.")
        _genai_client = OpenAI(
            base_url=base_url,
            api_key=api_key

        )
    return _genai_client


def get_chat_session(session_id=None, is_coach=False):
    """Initializes and returns an interactive chat object."""
    return AgentChatSession(settings.RAVEN_MODEL, session_id=session_id, is_coach=is_coach)
