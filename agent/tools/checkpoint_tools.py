import json
import os
import secrets
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent.utils import get_active_project_name, get_project_root
from agent.tools.file_tools import is_sensitive_file

IGNORE_DIRS = {
    'node_modules', '.git', 'venv', '.env', '.venv', 'env', '__pycache__',
    'dist', 'build', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.turbo', '.next', '.nuxt', '.cache', '.idea', '.vscode', '.vs',
    '.coverage', 'htmlcov'
}
IGNORE_EXTS = {'.pyc', '.pyo', '.pyd', '.png', '.jpg', '.jpeg', '.zip', '.tar', '.gz'}
MAX_BACKUP_FILE_SIZE = 2 * 1024 * 1024  # 2 MB per individual file


def _get_checkpoints_dir(project_name: Optional[str] = None) -> Path:
    """Returns the directory for storing checkpoints for the active project."""
    name = project_name or get_active_project_name() or "default"
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
    ckpt_dir = Path.home() / ".raven" / "checkpoints" / safe_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    return ckpt_dir


def _load_checkpoint_index(ckpt_dir: Path) -> List[Dict[str, Any]]:
    """Loads the checkpoint index list for the project."""
    index_file = ckpt_dir / "index.json"
    if not index_file.exists():
        return []
    try:
        return json.loads(index_file.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_checkpoint_index(ckpt_dir: Path, index_data: List[Dict[str, Any]]) -> None:
    """Saves the checkpoint index list for the project."""
    index_file = ckpt_dir / "index.json"
    try:
        index_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _is_git_repository(root_dir: Path) -> bool:
    """Checks if the project root is a git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def create_checkpoint(checkpoint_name: str = "") -> str:
    """
    Creates a transactional workspace snapshot/checkpoint before risky operations.
    Captures modified files, staged changes, and untracked files safely.

    Args:
        checkpoint_name: Descriptive label for the checkpoint (e.g., 'pre-refactor-auth', 'before-test-fix').
    Returns:
        Confirmation message with checkpoint ID and snapshot summary.
    """
    project_root = get_project_root()
    ckpt_dir = _get_checkpoints_dir()

    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    rand_suffix = secrets.token_hex(3)
    checkpoint_id = f"chk_{timestamp_str}_{rand_suffix}"
    label = checkpoint_name.strip() if checkpoint_name and checkpoint_name.strip() else f"checkpoint_{timestamp_str}"

    snapshot_path = ckpt_dir / checkpoint_id
    snapshot_path.mkdir(parents=True, exist_ok=True)

    is_git = _is_git_repository(project_root)
    head_commit = None
    modified_files = []
    untracked_files = []

    try:
        if is_git:
            # 1. Capture current HEAD commit
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if res.returncode == 0:
                    head_commit = res.stdout.strip()
            except Exception:
                head_commit = None

            # 2. Capture Git diff (staged + unstaged changes relative to HEAD)
            diff_text = ""
            try:
                diff_cmd = ["git", "diff", "HEAD"] if head_commit else ["git", "diff"]
                res = subprocess.run(
                    diff_cmd,
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=3.0,
                )
                if res.returncode == 0:
                    diff_text = res.stdout or ""
            except Exception:
                diff_text = ""

            # If there's staged changes separate from HEAD, make sure we capture them
            if diff_text:
                (snapshot_path / "diff.patch").write_text(diff_text, encoding="utf-8")

            # 3. Identify modified/staged files
            try:
                res_status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=2.0,
                )
                if res_status.returncode == 0:
                    for line in res_status.stdout.splitlines():
                        if not line.strip():
                            continue
                        status_code = line[:2]
                        file_rel = line[3:].strip().strip('"')
                        if status_code.startswith("?") or status_code.endswith("?"):
                            untracked_files.append(file_rel)
                        else:
                            modified_files.append(file_rel)
            except Exception:
                pass

            # 4. Backup untracked files
            untracked_backup_dir = snapshot_path / "untracked"
            for u_file in untracked_files:
                src_path = project_root / u_file
                if not src_path.is_file() or is_sensitive_file(u_file):
                    continue
                try:
                    if src_path.stat().st_size <= MAX_BACKUP_FILE_SIZE:
                        dst_path = untracked_backup_dir / u_file
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                except Exception:
                    continue

        else:
            # Non-git workspace backup
            files_backup_dir = snapshot_path / "files"
            for root, dirs, files in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.endswith(".egg-info")]
                for f in files:
                    p = Path(root) / f
                    if p.suffix.lower() in IGNORE_EXTS or is_sensitive_file(str(p)):
                        continue
                    try:
                        rel = p.relative_to(project_root)
                        if p.stat().st_size <= MAX_BACKUP_FILE_SIZE:
                            dst = files_backup_dir / rel
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(p, dst)
                            modified_files.append(rel.as_posix())
                    except Exception:
                        continue

        # Write metadata.json
        metadata = {
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": label,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "project_path": str(project_root),
            "is_git": is_git,
            "head_commit": head_commit,
            "modified_files": modified_files,
            "untracked_files": untracked_files,
            "total_files_captured": len(modified_files) + len(untracked_files),
        }
        (snapshot_path / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Update checkpoint index
        index = _load_checkpoint_index(ckpt_dir)
        index.insert(0, {
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": label,
            "timestamp": metadata["timestamp"],
            "total_files": metadata["total_files_captured"],
        })
        # Keep up to 50 checkpoints in index
        _save_checkpoint_index(ckpt_dir, index[:50])

        summary_parts = []
        if modified_files:
            summary_parts.append(f"{len(modified_files)} tracked file(s)")
        if untracked_files:
            summary_parts.append(f"{len(untracked_files)} untracked file(s)")
        state_summary = ", ".join(summary_parts) if summary_parts else "clean working tree"

        return (
            f"Successfully created checkpoint '{label}'\n"
            f"Checkpoint ID: {checkpoint_id}\n"
            f"Captured State: {state_summary}"
        )

    except Exception as e:
        return f"Failed to create checkpoint: {e}"


def rollback_checkpoint(checkpoint_id: Optional[str] = None) -> str:
    """
    Rolls back the workspace to a previously saved checkpoint.

    Args:
        checkpoint_id: Specific checkpoint ID to restore. If omitted, rolls back to the most recent checkpoint.
    Returns:
        Status message with the restored checkpoint details and affected files.
    """
    project_root = get_project_root()
    ckpt_dir = _get_checkpoints_dir()
    index = _load_checkpoint_index(ckpt_dir)

    if not index:
        return "Error: No checkpoints found for this project."

    target_id = checkpoint_id.strip() if checkpoint_id and checkpoint_id.strip() else ""
    if not target_id or target_id.lower() == "latest":
        target_id = index[0]["checkpoint_id"]

    snapshot_path = ckpt_dir / target_id
    meta_file = snapshot_path / "metadata.json"

    if not snapshot_path.exists() or not meta_file.exists():
        return f"Error: Checkpoint '{target_id}' not found."

    try:
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))
        label = metadata.get("checkpoint_name", target_id)
        timestamp = metadata.get("timestamp", "unknown time")
        is_git = metadata.get("is_git", False)

        restored_items = []

        if is_git and _is_git_repository(project_root):
            # 1. Clean untracked files added after the checkpoint
            try:
                res_untracked = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=2.0,
                )
                if res_untracked.returncode == 0:
                    current_untracked = [l.strip() for l in res_untracked.stdout.splitlines() if l.strip()]
                    saved_untracked = set(metadata.get("untracked_files", []))
                    for u_file in current_untracked:
                        if u_file not in saved_untracked:
                            target_del = project_root / u_file
                            if target_del.is_file() and not is_sensitive_file(u_file):
                                target_del.unlink(missing_ok=True)
            except Exception:
                pass

            # 2. Discard working changes to tracked files
            try:
                subprocess.run(
                    ["git", "checkout", "HEAD", "--", "."],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
            except Exception:
                pass

            # 3. Apply saved diff.patch if it existed
            diff_file = snapshot_path / "diff.patch"
            if diff_file.exists() and diff_file.stat().st_size > 0:
                try:
                    subprocess.run(
                        ["git", "apply", "--whitespace=nowarn", str(diff_file)],
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        timeout=3.0,
                    )
                except Exception:
                    pass

            # 4. Restore saved untracked files
            untracked_backup_dir = snapshot_path / "untracked"
            if untracked_backup_dir.exists():
                for root, _, files in os.walk(untracked_backup_dir):
                    for f in files:
                        b_file = Path(root) / f
                        rel = b_file.relative_to(untracked_backup_dir)
                        dst = project_root / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(b_file, dst)
                        restored_items.append(rel.as_posix())

            for mf in metadata.get("modified_files", []):
                if mf not in restored_items:
                    restored_items.append(mf)

        else:
            # Restore non-git files snapshot
            files_backup_dir = snapshot_path / "files"
            if files_backup_dir.exists():
                for root, _, files in os.walk(files_backup_dir):
                    for f in files:
                        b_file = Path(root) / f
                        rel = b_file.relative_to(files_backup_dir)
                        dst = project_root / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(b_file, dst)
                        restored_items.append(rel.as_posix())

        restored_count = len(restored_items)
        preview = ", ".join(restored_items[:3])
        if restored_count > 3:
            preview += f", ... (+{restored_count - 3} more)"

        summary = f"Restored {restored_count} file(s): {preview}" if restored_items else "Restored to clean state"

        return (
            f"Successfully rolled back to checkpoint '{label}'\n"
            f"Checkpoint ID: {target_id}\n"
            f"Original Timestamp: {timestamp}\n"
            f"{summary}"
        )

    except Exception as e:
        return f"Failed to rollback checkpoint '{target_id}': {e}"


def list_checkpoints(limit: int = 10) -> str:
    """
    Lists recent checkpoints created for this project.

    Args:
        limit: Maximum number of recent checkpoints to display (defaults to 10).
    Returns:
        Structured list of checkpoints with IDs, names, timestamps, and file counts.
    """
    ckpt_dir = _get_checkpoints_dir()
    index = _load_checkpoint_index(ckpt_dir)

    if not index:
        return "No checkpoints found for this project. Use create_checkpoint to create one."

    safe_limit = max(1, min(int(limit), 50))
    selected = index[:safe_limit]

    lines = [f"Checkpoints for project ({len(selected)} of {len(index)} total):"]
    for idx, item in enumerate(selected, 1):
        cid = item.get("checkpoint_id", "unknown")
        cname = item.get("checkpoint_name", "unnamed")
        ts = item.get("timestamp", "unknown")
        files_count = item.get("total_files", 0)
        lines.append(f"  {idx}. [{cid}] '{cname}' ({ts}) - {files_count} file(s)")

    return "\n".join(lines)
