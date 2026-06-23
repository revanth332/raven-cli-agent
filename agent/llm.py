# To run this code you need to install the following dependencies:
# pip install google-genai

from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

_genai_client = None
model = "gemini-flash-latest"
# model = "gemini-3-flash-preview"

tools = [
        types.Tool(googleSearch=types.GoogleSearch(
        )),
    ]

config = types.GenerateContentConfig(
    tools=tools,
    system_instruction=[
        types.Part.from_text(text=""""""),
    ])

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
    return client.chats.create(model=model,config=config)

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
        config=config
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
        config=config
    )

    return response.text

if __name__ == "__main__":
    print(get_response("Who are you?"))
