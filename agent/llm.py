# To run this code you need to install the following dependencies:
# pip install google-genai

from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import logging

from openai import OpenAI
from google.auth import default
import google.auth.transport.requests

# Suppress the automatic function calling warning from google-genai
logging.getLogger("google_genai").setLevel(logging.ERROR)

from agent.utils import get_memory_content,save_to_memory,read_file,patch_file,find_file,create_file,execute_command,save_concept,log_successful_debug,save_to_project_memory,get_project_memory,get_active_project_name,get_current_timestamp,get_repo_map,read_prompt_from_file,update_architecture_map,run_ui_test,get_llm_config,get_staged_git_changes,commit_staged_git_changes
from agent.indexer import search_codebase

load_dotenv()


def get_openai_tools():
    """
    Returns the list of 15 tools formatted in standard OpenAI tool JSON schema.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "save_to_memory",
                "description": "Save important facts, user preferences, project details, or newly learned concepts to long-term memory. Call this automatically when the user mentions something that would be useful for future interactions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "information": {
                            "type": "string",
                            "description": "The exact text or factual insight to be memorized."
                        },
                        "category": {
                            "type": "string",
                            "description": "The classification for this memory (e.g., 'preference', 'fact')."
                        }
                    },
                    "required": ["information", "category"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "save_to_project_memory",
                "description": "Save important facts, context, setup details, or architectural patterns specific to the CURRENT project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "description": "A short, concise fact about the current project to remember."
                        }
                    },
                    "required": ["fact"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "log_successful_debug",
                "description": "Logs a successfully resolved error and its detailed solution to global debug history for future reference.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "error_description": {
                            "type": "string",
                            "description": "The error message or description of the issue."
                        },
                        "solution": {
                            "type": "string",
                            "description": "The exact fix or steps taken to resolve the error."
                        }
                    },
                    "required": ["error_description", "solution"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "save_concept",
                "description": "Saves a detailed markdown explanation of a concept, design pattern, or architecture that the user is deeply exploring or has high interest in.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept_name": {
                            "type": "string",
                            "description": "The name of the concept or technology (e.g. 'React Context API', 'Docker Setup')."
                        },
                        "explanation": {
                            "type": "string",
                            "description": "A precise, organized explanation of the concept in markdown format."
                        }
                    },
                    "required": ["concept_name", "explanation"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_file",
                "description": "Search for a specific file in the current project directory. Accepts both simple filenames and relative/partial paths.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {
                            "type": "string",
                            "description": "The file name or exact partial relative path to search for."
                        }
                    },
                    "required": ["file_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "patch_file",
                "description": "Safely edit a file by replacing an exact, unique block of existing text with new text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The relative or absolute path of the file to edit."
                        },
                        "search_block": {
                            "type": "string",
                            "description": "The exact existing block of text in the file that needs to be replaced."
                        },
                        "replace_block": {
                            "type": "string",
                            "description": "The new text block that will replace the search_block."
                        }
                    },
                    "required": ["file_path", "search_block", "replace_block"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Full path of the file that needs to be read"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_file",
                "description": "Create a new file and write initial text content into it. Fails safely if the file already exists.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The relative or absolute path of the file to create."
                        },
                        "content": {
                            "type": "string",
                            "description": "The initial text content to write into the file. Defaults to an empty string."
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Executes a terminal command (CMD/PowerShell) on the user's Windows machine and returns the output.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The exact terminal command to execute."
                        }
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_timestamp",
                "description": "Get the exact current timestamp.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_architecture_map",
                "description": "Creates or updates the architecture.md file with a Mermaid.js diagram of the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mermaid_code": {
                            "type": "string",
                            "description": "The raw Mermaid.js graph code (e.g., 'graph TD\n A-->B'). Do not include markdown backticks."
                        },
                        "explanation": {
                            "type": "string",
                            "description": "A brief text explanation of the architecture."
                        }
                    },
                    "required": ["mermaid_code", "explanation"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_ui_test",
                "description": "Executes a Playwright Python script to perform UI automation, scraping, or E2E testing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "test_script": {
                            "type": "string",
                            "description": "The complete, runnable Python code using the Playwright sync API."
                        }
                    },
                    "required": ["test_script"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_codebase",
                "description": "Searches the codebase for code snippets or documentation related to the query. Use this to find how functions are implemented, where variables are defined, or general architectural context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The natural language question or code keywords to search for."
                        },
                        "top_results": {
                            "type": "integer",
                            "description": "Number of top results to return. Defaults to 3.",
                            "default": 3
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_staged_git_changes",
                "description": "Retrieve the current staged git changes.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "commit_staged_git_changes",
                "description": "Commit the code with a commit message. Commit can be verified or unverified.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Commit message related to the code changes"
                        },
                        "is_verified": {
                            "type": "boolean",
                            "description": "True/False to decide whether to include '--no-verify' in the commit command."
                        }
                    },
                    "required": ["message", "is_verified"]
                }
            }
        }
    ]

_genai_client = None
model_config = get_llm_config()
model = model_config.get("model","google/gemini-3-flash-preview")

class OpenRouterChatSession:
    def __init__(self,model_name,is_coach=False):
        self.model_name = model_name
        self.client = get_genai_client()

        global_memory = get_memory_content()
        project_memory = get_project_memory()
        project_name = get_active_project_name()
        repo_map = get_repo_map()
        COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.txt") if is_coach else ""

        self.system_prompt = read_prompt_from_file('prompts/system_prompt.txt').replace("{global_memory}", global_memory).replace("{project_name}", project_name).replace("{project_memory}", project_memory).replace("{repo_map}", repo_map).replace("{coach_prompt}", COACH_PROMPT)
        self.messages = [{"role":"system","content":self.system_prompt}]

    def send_message_stream(self,query):
        """
        Sends the current chat history stream. 
        If a query is passed, it appends it as a new user message first.
        If query is None, it continues the loop (e.g., passing back tool outputs).
        """
        if query is not None:
            self.messages.append({"role":"user","content":query})
        print(self.messages)
        tools = get_openai_tools()
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            tools=tools,
            stream=True
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
            msg["tool_calls"] = None
        self.messages.append(msg)

def get_model_config(is_coach:bool):
    client = get_genai_client()
    global_memory = get_memory_content()
    project_memory = get_project_memory()
    project_name = get_active_project_name()
    repo_map = get_repo_map()
    COACH_PROMPT = ""
    if is_coach:
        COACH_PROMPT = read_prompt_from_file("prompts/coach_prompt.txt")
    save_to_memory_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=save_to_memory
    )
    find_file_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=find_file
    )
    patch_file_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=patch_file
    )
    read_file_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=read_file
    )
    create_file_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=create_file
    )
    execute_command_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=execute_command
    )
    get_current_timestamp_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=get_current_timestamp
    )
    update_architecture_map_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=update_architecture_map
    )
    run_ui_test_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=run_ui_test
    )
    search_codebase_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=search_codebase
    )
    save_to_project_memory_dec = types.FunctionDeclaration.from_callable(
        client=client,
        callable=save_to_project_memory
    )
    log_successful_debug_dec = types.FunctionDeclaration.from_callable(
        client=client,
        callable=log_successful_debug
    )
    save_concept_dec = types.FunctionDeclaration.from_callable(
        client=client,
        callable=save_concept
    )
    get_staged_git_changes_dec = types.FunctionDeclaration.from_callable(
        client=client,
        callable=get_staged_git_changes
    )
    commit_staged_git_changes_dec = types.FunctionDeclaration.from_callable(
        client=client,
        callable=commit_staged_git_changes
    )
    tools = [
        # types.Tool(google_search=types.GoogleSearch),
        types.Tool(
            function_declarations=[
                save_to_memory_declaration,
                save_to_project_memory_dec,
                log_successful_debug_dec,
                save_concept_dec,
                find_file_declaration,
                patch_file_declaration,
                read_file_declaration,
                create_file_declaration,
                execute_command_declaration,
                get_current_timestamp_declaration,
                update_architecture_map_declaration,
                run_ui_test_declaration,
                search_codebase_declaration,
                get_staged_git_changes_dec,
                commit_staged_git_changes_dec
            ]),
            {"google_search": {}}
    ]
    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=[
            types.Part.from_text(text=read_prompt_from_file('prompts/system_prompt.txt')
                                .replace("{global_memory}", global_memory)
                                .replace("{project_name}", project_name)
                                .replace("{project_memory}", project_memory)
                                .replace("{repo_map}", repo_map)
                                .replace("{coach_prompt}", COACH_PROMPT)
            ),
        ])
    return config


def get_genai_client():
    global _genai_client

    if not _genai_client:
        api_key = None
        base_url = None
        if model.startswith("google/gemini-"):
            LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
            PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not PROJECT_ID or not LOCATION or not os.getenv("GOOGLE_GENAI_USE_VERTEXAI"):
                raise ValueError("Geni AI creds are missing!!!")

            credentials,_ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            credentials.refresh(google.auth.transport.requests.Request())
            api_key = credentials.token
            base_url = f"https://{LOCATION+'-' if LOCATION != 'global' else ''}aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/openapi"
        else:
            base_url = "https://openrouter.ai/api/v1"
            api_key = os.getenv("OPENROUTER_API_KEY")
        print(base_url)
        _genai_client = OpenAI(
            base_url=base_url,
            api_key=api_key

        )
    return _genai_client


def get_chat_session(is_coach=False):
    """Initializes and returns an interactive chat object."""
    return OpenRouterChatSession(model,is_coach)
    # client = get_genai_client()
    # return client.chat.completions.create(model=model,config=get_model_config(is_coach))

def get_streaming_response(query):
    client = get_genai_client()
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=query),
            ],
        )
    ]

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=get_model_config()
    ):
        if text := chunk.text:
            yield text


def get_response(query):
    """Handles one-off questions."""
    client = get_genai_client()
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=query),
            ],
        )
    ]

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=get_model_config()
    )

    return response.text

if __name__ == "__main__":
    print(get_response("Who are you?"))
