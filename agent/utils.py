def read_prompt_from_file(path:str):
    """
    Load a prompt from a text file into a single string.
    """
    try:
        with open(path,"r",encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at '{path}'. Exiting.")
        exit()
    except Exception as e:
        print(f"An unexpected error occurred while reading '{path}': {e}")
        exit()
