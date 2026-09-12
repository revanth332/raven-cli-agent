from pathlib import Path
import os
import shutil
import time
import json
import base64
import mimetypes
import io
from agent.core.settings import settings

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def encode_image_file(file_path: str | Path) -> dict:
    """
    Validates and encodes a local image file into a base64 Data URI.
    """
    try:
        clean_path = str(file_path).strip().strip('"').strip("'")
        path = Path(clean_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"Image file '{clean_path}' does not exist."
            }

        ext = path.suffix.lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
            return {
                "success": False,
                "error": f"Unsupported image format '{ext}'. Supported formats: {supported}"
            }

        size = path.stat().st_size
        if size > MAX_IMAGE_SIZE_BYTES:
            mb = size / (1024 * 1024)
            return {
                "success": False,
                "error": f"Image file is too large ({mb:.1f}MB). Maximum allowed size is 10MB."
            }

        mime_type, _ = mimetypes.guess_type(clean_path)
        if not mime_type:
            mime_type = "image/png" if ext == ".png" else "image/jpeg"

        data_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        return {
            "success": True,
            "data_uri": f"data:{mime_type};base64,{data_b64}",
            "mime_type": mime_type,
            "file_name": path.name,
            "size_bytes": size
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to encode image '{file_path}': {e}"
        }

def grab_clipboard_image() -> dict:
    """
    Extracts an image directly from the system clipboard (e.g. from Win+Shift+S)
    and encodes it as a base64 Data URI.
    """
    try:
        from PIL import ImageGrab, Image
        img = ImageGrab.grabclipboard()

        if img is None:
            return {
                "success": False,
                "error": "No image found in clipboard. Take a screenshot (Win+Shift+S) or copy an image first."
            }

        # Case 1: Copied file path(s) in Windows Explorer
        if isinstance(img, list):
            valid_paths = [p for p in img if Path(p).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]
            if valid_paths:
                return encode_image_file(valid_paths[0])
            return {
                "success": False,
                "error": f"Clipboard contains file paths but none are supported images: {img}"
            }

        # Case 2: Bitmap image in memory (screenshot)
        if isinstance(img, Image.Image):
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            size = len(img_bytes)

            if size > MAX_IMAGE_SIZE_BYTES:
                mb = size / (1024 * 1024)
                return {
                    "success": False,
                    "error": f"Clipboard image is too large ({mb:.1f}MB). Maximum allowed is 10MB."
                }

            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            return {
                "success": True,
                "data_uri": f"data:image/png;base64,{b64_data}",
                "mime_type": "image/png",
                "file_name": "clipboard_screenshot.png",
                "size_bytes": size,
                "width": img.width,
                "height": img.height
            }

        return {
            "success": False,
            "error": f"Unsupported clipboard content type: {type(img).__name__}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to access clipboard: {e}"
        }

def create_multimodal_content(text_prompt: str, image_data_uri: str) -> list[dict]:
    """
    Packages a text prompt and an image data URI into the OpenAI-compatible multimodal content format.
    """
    return [
        {"type": "text", "text": text_prompt or "Analyze this image."},
        {
            "type": "image_url",
            "image_url": {
                "url": image_data_uri
            }
        }
    ]

_files_backed_up_this_turn = set()

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

def get_active_project_name() -> str:
    """ 
    Determines the actual project root by walking up the directory tree and 
    looking for project markers (.git, package.json, etc.).
    Returns the name of the root folder.
    """
    current_dir = Path.cwd()
    root_markers = {'.git', 'package.json', 'pyproject.toml', 'requirements.txt'}
    for directory in [current_dir,*current_dir.parents]:
        if any((directory / marker).exists() for marker in root_markers):
            return directory.name
    return ""

def get_project_root() -> Path:
    """Returns the Path object for the root of the project."""
    current_dir = Path.cwd()
    root_markers = {'.git', 'package.json', 'pyproject.toml', 'requirements.txt'}
    
    for directory in [current_dir, *current_dir.parents]:
        if any((directory / marker).exists() for marker in root_markers):
            return directory
    return current_dir

def start_new_backup_turn():
    """
    Called every time the user hits Enter. Resets the backup tracker.
    """
    global _files_backed_up_this_turn
    _files_backed_up_this_turn.clear()

    registry_path = Path.home() / ".raven" / "backups" / "undo_registry.json"
    registry_path.parent.mkdir(parents=True,exist_ok=True)
    registry_path.write_text("[]",encoding="utf-8")

def backup_file(file_path:str):
    """
    Creates a backup file from the file path ONLY IF it hasn't been backed up yet this turn.
    """
    global _files_backed_up_this_turn
    try:
        original_file = Path(file_path)
        if not original_file.exists():
            return
        if str(original_file) in _files_backed_up_this_turn:
            return
        backup_dir = Path.home() / ".raven" / "backups"
        backup_dir.mkdir(parents=True,exist_ok=True)

        safe_name = f"{original_file.name}_{int(time.time())}"
        backup_file = backup_dir / safe_name

        shutil.copy2(original_file,backup_file)

        registry_file = backup_dir / "undo_registry.json"
        try:
            registry = json.loads(registry_file.read_text(encoding='utf-8'))
        except:
            registry = []
        registry.append({
            "original":str(original_file),
            "backup":str(backup_file)
        })
        
        registry_file.write_text(json.dumps(registry),encoding='utf-8')
        _files_backed_up_this_turn.add(str(original_file))
    except Exception as e:
        print(f"Failed to backup the file: {e}")

def get_repo_map(max_files: int = 250):
    """
    Get the full repo strucure
    """
    IGNORE_DIRS = {'node_modules', '.git', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build'}
    IGNORE_EXTS = {
        '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.dylib',
        '.mp4', '.mp3', '.wav', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.iso',
        '.env'
    }
    active_project = get_active_project_name()
    if not active_project:
        return ""
    file_paths = []
    for root,dirs,files in os.walk("."):
        # Skip standard ignore dirs and dynamically detect/skip custom virtual environments
        dirs[:] = [
            d for d in dirs 
            if d not in IGNORE_DIRS and not (Path(root) / d / "pyvenv.cfg").exists()
        ]
        for file in files:
            if any(file.lower().endswith(ext) for ext in IGNORE_EXTS):
                continue
            path = Path(root) / file
            file_paths.append(path.as_posix())

            if len(file_paths) >= max_files:
                file_paths.append(f"\n... (Output truncated: reached {max_files} file limit. Directory is too large. Use `find_file` tool to locate specific files.)")
                return "\n".join(file_paths)
    if not file_paths:
        return "No files found in the current directory"

    return "\n".join(file_paths)

def use_vertex_ai():
    return str(settings.RAVEN_USE_VERTEX_AI).strip().lower() == "true"
