from dotenv import load_dotenv
import logging

from openai import OpenAI
from google.auth import default
import google.auth.transport.requests

# Suppress the automatic function calling warning from google-genai
logging.getLogger("google_genai").setLevel(logging.ERROR)

from agent.utils import get_active_project_name,get_repo_map,read_prompt_from_file
from agent.tools.memory_tools import get_memory_content,get_project_memory
from agent.tools.tool_registry import raven_tools
from agent.core.settings import settings

load_dotenv()

_genai_client = None


class AgentChatSession:
    def __init__(self,model_name,is_coach=False):
        self.model_name = model_name
        self.client = get_genai_client()

        global_memory = get_memory_content()
        project_memory = get_project_memory()
        project_name = get_active_project_name()
        repo_map = get_repo_map()
        COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.md") if is_coach else ""

        self.system_prompt = read_prompt_from_file('prompts/system_prompt.md').replace("{global_memory}", global_memory).replace("{project_name}", project_name).replace("{project_memory}", project_memory).replace("{repo_map}", repo_map).replace("{coach_prompt}", COACH_PROMPT)
        self.messages = [{"role":"system","content":self.system_prompt}]

    def send_message_stream(self,query):
        """
        Sends the current chat history stream. 
        If a query is passed, it appends it as a new user message first.
        If query is None, it continues the loop (e.g., passing back tool outputs).
        """
        if query is not None:
            self.messages.append({"role":"user","content":query})
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            tools=raven_tools,
            stream=True,
        )

        return response
    def add_message(self,role,content=None,tool_call_id=None,name=None,tool_calls=None):
        """Helper to append structured assistant or tool returns to history"""
        msg = {"role":role}
        if content is not None:
            msg["content"] = content
        if tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id
        if name is not None:
            msg["name"] = name
        if tool_calls is not None:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)


def get_genai_client():
    global _genai_client

    if not _genai_client:
        api_key = None
        base_url = settings.RAVEN_BASE_URL
        if str(settings.RAVEN_USE_VERTEX_AI).strip().lower() == "true":
            credentials,_ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            credentials.refresh(google.auth.transport.requests.Request())
            api_key = credentials.token
        else:
            api_key = settings.RAVEN_API_KEY

        if not api_key or not base_url:
            raise ValueError("Credentials are missing!!! Please use 'config' command to configure the credentials.")
        _genai_client = OpenAI(
            base_url=base_url,
            api_key=api_key

        )
    return _genai_client


def get_chat_session(is_coach=False):
    """Initializes and returns an interactive chat object."""
    return AgentChatSession(settings.RAVEN_MODEL,is_coach)
