from agent.tools.memory_tools import save_to_memory,save_concept,log_successful_debug,save_to_project_memory,update_architecture_map
from agent.tools.file_tools import find_file,read_file,create_file,patch_file
from agent.tools.git_tools import get_staged_git_changes,commit_staged_git_changes,get_git_status,git_add,get_git_diff
from agent.tools.miscellaneous_tools import execute_command,get_current_timestamp
from agent.core.indexer import search_codebase

raven_tools = [
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
                "required": [
                    "information",
                    "category"
                ]
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
                "required": [
                    "fact"
                ]
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
                "required": [
                    "error_description",
                    "solution"
                ]
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
                "required": [
                    "concept_name",
                    "explanation"
                ]
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
                "required": [
                    "file_name"
                ]
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
                "required": [
                    "file_path",
                    "search_block",
                    "replace_block"
                ]
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
                "required": [
                    "file_path"
                ]
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
                "required": [
                    "file_path"
                ]
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
                "required": [
                    "command"
                ]
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
                "required": [
                    "mermaid_code",
                    "explanation"
                ]
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
                "required": [
                    "query"
                ]
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
                    }
                },
                "required": [
                    "message"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_status",
            "description": "Retrieve the current git status of the repository, including staged, unstaged, and untracked files.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Stage files or directories for the next git commit (git add).",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of file paths or patterns to stage. Default is ['.'] to stage all changes."
                    }
                },
                "required": [
                    "files"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_diff",
            "description": "Retrieve git diff output showing working directory (unstaged) or staged changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Optional specific file path to inspect diff for."
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "If true, shows staged changes (--cached). Defaults to false."
                    }
                },
                "required": []
            }
        }
    }
]

TOOL_REGISTRY = {
    "save_to_memory": {
        "fn": save_to_memory, 
        "display_name": "Remember", 
        "display_arg": "", 
        "ignore_display": False
    },
    "find_file": {
        "fn": find_file, 
        "display_name": "Find", 
        "display_arg": "file_name",
        "ignore_display": True
    },
    "read_file": {
        "fn": read_file, 
        "display_name": "Read", 
        "display_arg": "file_path", 
        "ignore_display": False
    },
    "create_file": {
        "fn": create_file, 
        "display_name": "Create", 
        "display_arg": "file_path", 
        "ignore_display": False
    },
    "execute_command": {
        "fn": execute_command, 
        "display_name": "Execute", 
        "display_arg": "command", 
        "ignore_display": False
    },
    "get_current_timestamp": {
        "fn": get_current_timestamp, 
        "display_name": "Time", 
        "display_arg": None, 
        "ignore_display": True
    },
    "save_concept": {
        "fn": save_concept, 
        "display_name": "Document Concept", 
        "display_arg": "concept_name", 
        "ignore_display": False
    },
    "log_successful_debug": {
        "fn": log_successful_debug, 
        "display_name": "Log Fix", 
        "display_arg": "error_description", 
        "ignore_display": False
    },
    "save_to_project_memory": {
        "fn": save_to_project_memory, 
        "display_name": "Project Memory", 
        "display_arg": "fact", 
        "ignore_display": False
    },
    "patch_file": {
        "fn": patch_file, 
        "display_name": "Patch", 
        "display_arg": "file_path", 
        "ignore_display": True
    },
    "update_architecture_map": {
        "fn": update_architecture_map, 
        "display_name": "Update Architecture Map", 
        "display_arg": None,
        "ignore_display": False
    },
    "search_codebase":{
        "fn": search_codebase,
        "display_name": "Searching Codebase",
        "display_arg": "",
        "ignore_display": False
    },
    "get_staged_git_changes":{
        "fn": get_staged_git_changes,
        "display_name": "Search changes",
        "display_arg": "",
        "ignore_display": False
    },
    "commit_staged_git_changes":{
        "fn": commit_staged_git_changes,
        "display_name": "Commit changes",
        "display_arg": ["message"],
        "ignore_display": False
    },
    "get_git_status":{
        "fn": get_git_status,
        "display_name": "Git Status",
        "display_arg": "",
        "ignore_display": False
    },
    "git_add":{
        "fn": git_add,
        "display_name": "Git Add",
        "display_arg": "files",
        "ignore_display": False
    },
    "get_git_diff":{
        "fn": get_git_diff,
        "display_name": "Git Diff",
        "display_arg": "file_path",
        "ignore_display": False
    },
}
