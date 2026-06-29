# To run this code you need to install the following dependencies:
# pip install google-genai

from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

from agent.utils import get_memory_content,save_to_memory,read_file,write_file,find_file,create_file,execute_command

load_dotenv()

_genai_client = None
model = "gemini-flash-latest"
# model = "gemini-3-flash-preview"

def get_llm_config():
    client = get_genai_client()
    memory_content = get_memory_content()
    save_to_memory_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=save_to_memory
    )
    find_file_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=find_file
    )
    write_file_declaration = types.FunctionDeclaration.from_callable(
        client=client,
        callable=write_file
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
    tools = [
        # types.Tool(google_search=types.GoogleSearch),
        types.Tool(function_declarations=[save_to_memory_declaration,find_file_declaration,write_file_declaration,read_file_declaration,create_file_declaration,execute_command_declaration])
    ]
    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=[
            types.Part.from_text(text=f"""
                {memory_content}
                CRITICAL INSTRUCTION:
                1. If you found a new preference, a project detail, or learning new concept during the conversation with the user interactions like doubts resolving, code commiting etc., you MUST use the `save_to_memory` tool to remember it. For example if a user asks a question related to a new concept then save those details into memory as learning with max 2 lines only mentioning that user learnt this concept. If he commits something then based on the code save the task details into memory etc. It should be like a smart history,
                2. You have the power to navigate and read/write files in the local directory. Use these tools autonomously to solve developer tasks.
                3. You can execute terminal commands on the user's Windows machine to run tests, check git status, build projects, or spin up servers.
            """
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
