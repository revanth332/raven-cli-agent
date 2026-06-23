from pathlib import Path
def read_prompt_from_file(path:str):
    """
    Load a prompt from a text file into a single string.
    """
    agent_dir = Path(__file__).parent
    file_path = agent_dir / path
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: Prompt file not found at '{file_path}'. Exiting.")
        exit()
    except Exception as e:
        print(f"An unexpected error occurred while reading '{file_path}': {e}")
        exit()
