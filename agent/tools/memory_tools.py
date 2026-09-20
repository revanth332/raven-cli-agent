from pathlib import Path
import os
from agent.utils import get_project_root,get_active_project_name,use_vertex_ai
from agent.core.settings import settings

def chunk_debug_history(text: str) -> list[dict]:
    """
    Splits debug history into distinct logical chunks per error.
    """
    chunks = []
    sections = text.split("## Error:")
    for idx, sec in enumerate(sections):
        sec_content = sec.strip()
        if not sec_content:
            continue
        if sec_content.startswith("#"):
            continue
        chunks.append({
            "type": "debug_log",
            "content": f"## Error: {sec_content}"
        })
    return chunks

def chunk_markdown_file(file_path: Path, text: str) -> list[dict]:
    """
    Chunks standard markdown text by paragraph groupings under 1000 characters.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    chunk_idx = 0
    for p in paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        if len(current_chunk) + len(p_strip) < 1000:
            current_chunk += p_strip + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append({
                    "type": "concept_block" if "concepts" in str(file_path) else "global_memory_block",
                    "content": current_chunk.strip()
                })
                chunk_idx += 1
            current_chunk = p_strip + "\n\n"
    if current_chunk.strip():
        chunks.append({
            "type": "concept_block" if "concepts" in str(file_path) else "global_memory_block",
            "content": current_chunk.strip()
        })
    return chunks

def get_episodic_vector_db():
    """
    Initializes and returns the global episodic memory ChromaDB collection.
    """
    embedding_model = getattr(settings, "RAVEN_EMBEDDING_MODEL", None) or getattr(settings, "EMBEDDING_MODEL", None)
    if not embedding_model or not use_vertex_ai():
        return None
    import chromadb
    from agent.core.indexer import GeminiEmbeddingFunction
    db_path = Path.home() / ".raven" / "vector_db" / "global_episodic"
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(
        name="raven_episodic_memory",
        embedding_function=GeminiEmbeddingFunction()
    )
    return collection

def index_episodic_memory():
    """
    Indexes global memory, debug logs, and technical concepts to ChromaDB if modified.
    """
    embedding_model = getattr(settings, "RAVEN_EMBEDDING_MODEL", None) or getattr(settings, "EMBEDDING_MODEL", None)
    if not embedding_model or not use_vertex_ai():
        return

    collection = get_episodic_vector_db()
    if not collection:
        return

    global_memory_file = Path.home() / ".raven" / "memory" / "global_memory.md"
    debug_history_file = Path.home() / ".raven" / "debug_history.md"
    concepts_dir = Path.home() / ".raven" / "concepts"

    existing_docs = collection.get(include=["metadatas"])
    existing_files_mtime = {}
    if existing_docs and existing_docs["metadatas"]:
        for meta in existing_docs["metadatas"]:
            if "file_path" in meta and "mtime" in meta:
                existing_files_mtime[meta["file_path"]] = meta["mtime"]

    documents = []
    metadatas = []
    ids = []
    current_files = set()

    files_to_index = []
    if global_memory_file.exists():
        files_to_index.append((global_memory_file, "global_memory"))
    if debug_history_file.exists():
        files_to_index.append((debug_history_file, "debug_history"))

    if concepts_dir.exists():
        for f in concepts_dir.iterdir():
            if f.is_file() and f.name.endswith(".md"):
                files_to_index.append((f, "concept"))

    for f_path, f_type in files_to_index:
        f_str = str(f_path).replace("\\", "/")
        current_files.add(f_str)
        try:
            mtime = os.path.getmtime(f_path)
            if f_str in existing_files_mtime and existing_files_mtime[f_str] == mtime:
                continue

            content = f_path.read_text(encoding="utf-8")
            if f_type == "debug_history":
                chunks = chunk_debug_history(content)
            else:
                chunks = chunk_markdown_file(f_path, content)

            for idx, chunk in enumerate(chunks):
                chunk_id = f"{f_str}::{chunk['type']}::{idx}"
                documents.append(chunk["content"])
                metadatas.append({
                    "file_path": f_str,
                    "type": chunk["type"],
                    "mtime": mtime
                })
                ids.append(chunk_id)
        except Exception:
            pass

    deleted_files = set(existing_files_mtime.keys()) - current_files
    for deleted_f in deleted_files:
        try:
            collection.delete(where={"file_path": deleted_f})
        except Exception:
            pass
    batch_size = 100
    if documents:
        for i in range(0,len(documents),batch_size):
            collection.upsert(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )

def recall_memory(query: str) -> str:
    """
    Searches your global memory, debug history, and documented concepts for relevant past experiences, debug solutions, and technical insights.
    Args:
        query: Semantic query matching past experiences, errors, or concepts.
    """
    embedding_model = getattr(settings, "RAVEN_EMBEDDING_MODEL", None) or getattr(settings, "EMBEDDING_MODEL", None)
    if not embedding_model or not use_vertex_ai():
        return "Tool is not supported."
    index_episodic_memory()
    collection = get_episodic_vector_db()
    if not collection:
        return "No episodic memory collection found."

    try:
        result = collection.query(
            query_texts=[query],
            n_results=3
        )
    except Exception as e:
        return f"Error querying episodic memory: {e}"

    if not result or not result["documents"] or not result["documents"][0]:
        return "No relevant past memories, debug solutions, or concepts found."

    formatted_results = []
    for index in range(len(result["documents"][0])):
        doc = result["documents"][0][index]
        meta = result["metadatas"][0][index]
        source_name = Path(meta["file_path"]).name
        formatted_results.append(
            f"### Source: {source_name} (Type: {meta['type']})\n\n{doc}"
        )

    return "\n\n---\n\n".join(formatted_results)

def get_memory_content():
    """
    Load Global memory content from the memory file if exists or creates a memory file.
    """
    memory_file = Path.home() / ".raven" / "memory" / "global_memory.md"

    if not memory_file.exists():
        memory_file.parent.mkdir(parents=True,exist_ok=True)
        default_memory = "You are Raven, my personal AI developer agent. Here is what you know about me:\n\n- I use Windows.\n- My main stack is React, Node, and Python."
        memory_file.write_text(default_memory,encoding='utf-8')
    return memory_file.read_text(encoding='utf-8')

def get_project_memory_info():
    """Loads or initializes memory specific to the active project folder."""
    project_name = get_active_project_name()
    if not project_name:
        return "","No memory available yet."
    project_memory_file = Path.home() / ".raven" / "memory" / "projects" / (project_name + ".md")
    if not project_memory_file.exists():
        project_memory_file.parent.mkdir(parents=True,exist_ok=True)
        default_project_memory = f"# {project_name} - Architecture & Operational Context\n\n## Tech Stack & Runtime\n\n## Active Architecture & Key Modules\n\n## Critical Constraints\n\n## Preferences\n\n## Current/Ongoing Tasks\n"
        project_memory_file.write_text(default_project_memory, encoding="utf-8")
    return str(project_memory_file),project_memory_file.read_text(encoding='utf-8')

def get_active_projects():
    """
    Use this tool to get the paths of active projects.

    Returns:
    Full paths of the active projects memory files
    """
    projects = []
    projects_memory_folder = Path.home() / ".raven" / "memory" / "projects"
    if not projects_memory_folder.exists():
        return "No Projects available."
    for file in projects_memory_folder.iterdir():
        if file.is_file() and file.name.endswith(".md"):
            projects.append(str(file))
    if len(projects) <= 0:
        return "No Projects available."
    return projects


def save_to_memory(information:str,category:str):
    """
    Use this tool to save important facts, user preferences, project details, or newly learned concepts to long-term memory.
    Call this automatically when the user mentions something that would be useful for future interactions.
    Args:
        information: The exact text or factual insight to be memorized.
        category: The classification for this memory (e.g., 'preference', 'fact').
    """
    memory_file = Path.home() / ".raven" / "memory" / "global_memory.md"
    with open(memory_file,'a',encoding='utf-8') as f:
        f.write(f"\n-{category}: {information}")
    return "New data added to memory successfully"

      
def log_successful_debug(error_description: str, solution: str) -> str:
    """
    Logs a successfully resolved error and its detailed solution to global debug history for future reference.
    Args:
        error_description: The error message or description of the issue.
        solution: The exact fix or steps taken to resolve the error.
    """
    debug_file = Path.home() / ".raven" / "debug_history.md"
    
    if not debug_file.exists():
        debug_file.parent.mkdir(parents=True, exist_ok=True)
        debug_file.write_text("# Debugging History & Error Resolutions\n\n", encoding="utf-8")
        
    project_name = get_active_project_name()
    log_entry = f"\n## Error: {error_description}\n- **Project**: {project_name}\n- **Solution**: {solution}\n"
    if not project_name:
        log_entry = f"\n## Error: {error_description}\n- **Solution**: {solution}\n"
    
    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
    return "Debug session successfully logged in global history."

def save_concept(concept_name: str, explanation: str) -> str:
    """
    Saves a detailed markdown explanation of a concept, design pattern, or architecture that the user is deeply exploring or has high interest in.
    Args:
        concept_name: The name of the concept or technology (e.g. 'React Context API', 'Docker Setup').
        explanation: A precise, organized explanation of the concept in markdown format.
    """
    # Clean filename (e.g., "React Context API" -> "react_context_api.md")
    safe_name = concept_name.lower().replace(" ", "_")
    concept_file = Path.home() / ".raven" / "concepts" / f"{safe_name}.md"
    
    concept_file.parent.mkdir(parents=True, exist_ok=True)
    concept_file.write_text(f"# Concept: {concept_name}\n\n{explanation}\n", encoding="utf-8")
    return f"Concept '{concept_name}' successfully documented."

def update_architecture_map(mermaid_code: str, explanation: str):
    """
    Creates or updates the architecture.md file with a Mermaid.js diagram of the project.
    Args:
        mermaid_code: The raw Mermaid.js graph code (e.g., 'graph TD\n A-->B'). Do not include markdown backticks.
        explanation: A brief text explanation of the architecture.
    """
    try:
        active_dir = get_project_root()
        if not active_dir:
            return "No active project directory found."
        archtecture_file = active_dir / 'architecture.md'
        content = f"Project architecture:\n\n {explanation} \n\n ```mermaid\n{mermaid_code}\n```\n"
        archtecture_file.write_text(content,'utf-8')
        return f"Successfully generated architecture map at {archtecture_file.name}."
    except Exception as e:
        return f"Failed to update architecture map: {e}"
