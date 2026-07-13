import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import os
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from pathlib import Path

def get_parser_and_query(ext:str):
    """Factory function that returns the correct Tree-sitter parser and AST query for a given language."""
    language = None
    query_string = None
    if ext == ".py":
        language = Language(tspython.language())
        query_string = """
        (class_definition) @class
        (function_definition) @function
        """
    elif ext in [".js",".jsx"]:
        language = Language(tsjavascript.language())
        query_string = """
        (class_declaration) @class
        (function_declaration) @function
        (method_definition) @method
        (variable_declarator name: (identifier) value: (arrow_function)) @function
        """
    elif ext in [".ts",".tsx"]:
        if ext == ".tsx":
            language = Language(tstypescript.language_tsx())
        else:
            language = Language(tstypescript.language_typescript())
        query_string = """
        (class_declaration) @class
        (interface_declaration) @interface
        (function_declaration) @function
        (method_definition) @method
        (variable_declarator name: (identifier) value: (arrow_function)) @function
        """
    
    if language:
        return language,query_string,Parser(language)
    raise ValueError(f"Unsupported extension: {ext}") 

def chunk_code_file(file_path:str,code:str,ext:str):
    """
    Parses Python code into semantic chunks (functions and classes) using an Abstract Syntax Tree.
    Returns a list of dictionaries containing the chunk's text and metadata.
    """
    LANGUAGE,query_string,parser = get_parser_and_query(ext)
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)

    query = Query(LANGUAGE,query_string)
    query_cursor = QueryCursor(query)
    captures = query_cursor.captures(tree.root_node)

    chunks = []

    for capture_name,nodes in captures.items():
        for node in nodes:
            chunk_text = code_bytes[node.start_byte:node.end_byte].decode("utf-8")
            
            identifier_node = None
            for child in node.children:
                if child.type in ["identifier", "property_identifier", "type_identifier"]:
                    identifier_node = child
                    break
            chunk_name = code_bytes[identifier_node.start_byte:identifier_node.end_byte].decode("utf-8") if identifier_node else "unknown"

            chunks.append({
                "file_path":file_path,
                "type":capture_name,
                "name":chunk_name,
                "content":chunk_text,
            })
    return chunks

def chunk_text_file(file_path: str, text: str, max_chunk_size: int = 1000) -> list[dict]:
    """
    Chunks plain text and markdown files by paragraphs to prevent breaking sentences.
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    chunk_index = 0
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < max_chunk_size:
            current_chunk += p + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append({
                    "file_path": file_path,
                    "type": "documentation",
                    "name": f"text_block_{chunk_index}",
                    "content": current_chunk.strip()
                })
                chunk_index += 1
            current_chunk = p + "\n\n"
            
    # Don't forget the last leftover chunk!
    if current_chunk.strip():
        chunks.append({
            "file_path": file_path,
            "type": "documentation",
            "name": f"text_block_{chunk_index}",
            "content": current_chunk.strip()
        })
        
    return chunks

class GeminiEmbeddingFunction(EmbeddingFunction):
    """Custom ChromaDB embedding function that uses Google's text-embedding-004."""
    def __init__(self):
        pass
    def __call__(self,input:Documents):
        from agent.llm import get_genai_client
        client = get_genai_client()
        
        response = client.models.embed_content(model="text-embedding-004",contents=input)

        return [e.values for e in response.embeddings]

def get_vector_db():
    """Initializes and returns the ChromaDB client and codebase collection."""
    from agent.utils import get_active_project_name
    active_project = get_active_project_name()
    if active_project:
        db_path = Path.home() / ".raven" / "vector_db" / active_project
        client = chromadb.PersistentClient(path=db_path)

        collection = client.get_or_create_collection(
            name="codebase",
            embedding_function=GeminiEmbeddingFunction()
        )
        return collection
    return None

def index_project():
    """Scans the project, chunks Python files, and adds them to ChromaDB."""
    collection = get_vector_db()

    if not collection:
        print("Unable to find a project to index")

    IGNORE_DIRS = {'node_modules', '.git', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build', '.agents'}
    CODE_EXTS = (".py", ".js", ".jsx", ".ts", ".tsx")
    DOC_EXTS = (".md", ".txt")
    documents = []
    metadatas = []
    ids = []

    print("Scanning project for Python files...")

    existing_docs = collection.get(include=["metadatas"])
    existing_files_mtime= {}
    current_disk_files = set()
    if existing_docs and existing_docs["metadatas"]:
        for meta in existing_docs["metadatas"]:
            if "file_path" in meta and "mtime" in meta:
                existing_files_mtime[meta['file_path']] = meta["mtime"]
    
    for root,dirs,files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file.endswith(CODE_EXTS+DOC_EXTS):
                file_path = str(Path(root) / file).replace("\\","/")
                current_disk_files.add(file_path)
                try:
                    mtime = os.path.getmtime(file_path)
                    if file_path in existing_files_mtime and existing_files_mtime[file_path] == mtime:
                        continue
                    with open(file_path,'r',encoding='utf-8') as f:
                        content = f.read()
                    if file.endswith(CODE_EXTS):
                        ext = Path(file).suffix
                        chunks = chunk_code_file(file_path,content,ext)
                    else:
                        chunks = chunk_text_file(file_path,content,ext)

                    for chunk in chunks:
                        chunk_id = f"{file_path}::{chunk['type']}::{chunk['name']}"
                        documents.append(chunk['content'])
                        metadatas.append({
                                "file_path": chunk['file_path'],
                                "type": chunk['type'],
                                "name": chunk['name'],
                                "mtime": mtime
                        })
                        ids.append(chunk_id)
                except Exception as e:
                    print(f"Skipping {file_path} due to error: {e}")

    # cleaning up the deleted files
    deleted_files = set(existing_files_mtime.keys()) - current_disk_files
    for file in deleted_files:
        collection.delete(where={file_path:file})
        print(f"Removed deleted file from index: {file}")
    
    if not current_disk_files:
        print("No valid Python chunks found to index.")

    if documents:
        print(f"Embedding and Indexing {len(documents)} semantic chunks...")
        # Upsert adds new chunks and overwrites old ones if the ID matches
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print("Indexing complete!")
    else:
        print("Index is already up to date. No changes detected.")

def search_codebase(query:str,top_results:int = 3):
    """
    Searches the codebase for code snippets or documentation related to the query.
    Use this to find how functions are implemented, where variables are defined, or general architectural context.
    Args:
        query: The natural language question or code keywords to search for.
    """
    collection = get_vector_db()

    result = collection.query(
        query_texts=[query],
        n_results=top_results
    )

    if not result["documents"] or not result["documents"][0]:
        return "No relevant code or documentation found."
    
    formatted_results = []
    for index in range(len(result["documents"][0])):
        doc = result["documents"][0][index]
        meta = result["metadatas"][0][index]

        header = f"File: {meta['file_path']} | Type: {meta['type']} | Name: {meta['name']}"
        formatted_results.append(f"{header}\n ```python\n{doc}\n```")
    
    return "\n\n".join(formatted_results)


if __name__ == "__main__":
    # code = ""
    # with open("agent/main.py",'r',encoding='utf-8') as f:
    #     code = f.read()
    
    chunks = chunk_code_file("indexer.py","""const ASTRA_ROLE_PREFIXES = ['ROLE_ASTRA_'];
const YANTRA_ROLE_PREFIXES = ['ROLE_IOPS_'];

interface RoleCategory = 'astra-only' | 'yantra-only' | 'mixed' | 'none';

export const hasAstraRoles = (roles: string[]): boolean =>
  roles.some(role => ASTRA_ROLE_PREFIXES.some(prefix => role.startsWith(prefix)));

export const hasYantraRoles = (roles: string[]): boolean =>
  roles.some(role => YANTRA_ROLE_PREFIXES.some(prefix => role.startsWith(prefix)));

export const classifyRoles = (roles: string[]): RoleCategory => {
  if (!roles || roles.length === 0) return 'none';

  const astra = hasAstraRoles(roles);
  const yantra = hasYantraRoles(roles);

  if (astra && yantra) return 'mixed';
  if (astra) return 'astra-only';
  if (yantra) return 'yantra-only';

  return 'none';
};
""",".tsx")
    for i,chunk in enumerate(chunks):
        chunk['content'] = chunk['content'][:100]+"..."
        print(f"chunk {i+1} --> {chunk}\n")
    # index_project()
    # search_codebase("modify report command",2)