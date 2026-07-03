# To run this code you need to install the following dependencies:
# pip install google-genai

from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

from agent.utils import get_memory_content,save_to_memory,read_file,patch_file,find_file,create_file,execute_command,save_concept,log_successful_debug,save_to_project_memory,get_project_memory,get_active_project_name,get_current_timestamp,get_repo_map,read_prompt_from_file

load_dotenv()

_genai_client = None
model = "gemini-flash-latest"
# model = "gemini-3-flash-preview"

def get_llm_config():
    client = get_genai_client()
    global_memory = get_memory_content()
    project_memory = get_project_memory()
    project_name = get_active_project_name()
    repo_map = get_repo_map()
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
    save_to_project_memory_dec = types.FunctionDeclaration.from_callable(client=client, callable=save_to_project_memory)
    log_successful_debug_dec = types.FunctionDeclaration.from_callable(client=client, callable=log_successful_debug)
    save_concept_dec = types.FunctionDeclaration.from_callable(client=client, callable=save_concept)
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
                get_current_timestamp_declaration
            ])
    ]
    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=[
            types.Part.from_text(text=read_prompt_from_file('prompts/system_prompt.txt').format(
                global_memory=global_memory,
                project_name=project_name,
                project_memory=project_memory,
                repo_map=repo_map
            )
            ),
        ])
    return config


def get_genai_client():
    global _genai_client

    if not _genai_client:
        if not os.getenv("GOOGLE_CLOUD_PROJECT") or not os.getenv("GOOGLE_CLOUD_LOCATION") or not os.getenv("GOOGLE_GENAI_USE_VERTEXAI"):
            raise ValueError("Geni AI creds are missing!!!")
        _genai_client = genai.Client()
    return _genai_client

def get_chat_session():
    """Initializes and returns an interactive chat object."""
    client = get_genai_client()
    return client.chats.create(model=model,config=get_llm_config())

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
        config=get_llm_config()
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
        config=get_llm_config()
    )

    return response.text

if __name__ == "__main__":
    print(get_response("Who are you?"))
