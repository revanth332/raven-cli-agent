import json
import subprocess
from pathlib import Path
from agent.tools.checkpoint_tools import (
    create_checkpoint,
    rollback_checkpoint,
    list_checkpoints,
)
from agent.tools.tool_registry import TOOL_REGISTRY, raven_tools


def test_create_and_rollback_non_git(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.tools.checkpoint_tools.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("agent.tools.checkpoint_tools._get_checkpoints_dir", lambda project_name=None: tmp_path / ".checkpoints")

    # 1. Setup workspace files
    file1 = tmp_path / "app.py"
    file1.write_text("INITIAL_VERSION = 1\n", encoding="utf-8")
    sub_dir = tmp_path / "pkg"
    sub_dir.mkdir()
    file2 = sub_dir / "helper.py"
    file2.write_text("def help(): pass\n", encoding="utf-8")

    # 2. Create checkpoint
    res_create = create_checkpoint("baseline")
    assert "Successfully created checkpoint" in res_create
    assert "baseline" in res_create

    # 3. Make destructive changes
    file1.write_text("CORRUPTED_CODE = True\n", encoding="utf-8")
    file2.unlink()
    new_file = tmp_path / "unwanted.py"
    new_file.write_text("unwanted content\n", encoding="utf-8")

    # 4. Rollback
    res_rollback = rollback_checkpoint()
    assert "Successfully rolled back" in res_rollback

    # 5. Verify restoration
    assert file1.read_text(encoding="utf-8") == "INITIAL_VERSION = 1\n"
    assert file2.exists()
    assert file2.read_text(encoding="utf-8") == "def help(): pass\n"


def test_create_and_rollback_git(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.tools.checkpoint_tools.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("agent.tools.checkpoint_tools._get_checkpoints_dir", lambda project_name=None: tmp_path / ".checkpoints")

    # Init git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), capture_output=True, check=True)

    f1 = tmp_path / "code.py"
    f1.write_text("def start(): return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), capture_output=True, check=True)

    # Modify code and add untracked file before checkpoint
    f1.write_text("def start(): return 2\n", encoding="utf-8")
    f_untracked = tmp_path / "extra.py"
    f_untracked.write_text("EXTRA = True\n", encoding="utf-8")

    # Create checkpoint
    res_create = create_checkpoint("git-checkpoint-1")
    assert "Successfully created checkpoint" in res_create

    # Corrupt code and add unwanted new file
    f1.write_text("BROKEN\n", encoding="utf-8")
    f_bad = tmp_path / "bad.txt"
    f_bad.write_text("bad\n", encoding="utf-8")

    # Rollback
    res_rollback = rollback_checkpoint()
    assert "Successfully rolled back" in res_rollback
    assert f1.read_text(encoding="utf-8") == "def start(): return 2\n"
    assert f_untracked.exists()
    assert not f_bad.exists()


def test_list_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.tools.checkpoint_tools.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("agent.tools.checkpoint_tools._get_checkpoints_dir", lambda project_name=None: tmp_path / ".checkpoints")

    res_empty = list_checkpoints()
    assert "No checkpoints found" in res_empty

    create_checkpoint("step-1")
    create_checkpoint("step-2")

    res_list = list_checkpoints()
    assert "step-1" in res_list
    assert "step-2" in res_list


def test_rollback_invalid_id(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.tools.checkpoint_tools.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("agent.tools.checkpoint_tools._get_checkpoints_dir", lambda project_name=None: tmp_path / ".checkpoints")

    res = rollback_checkpoint("chk_nonexistent_12345")
    assert "Error:" in res


def test_tool_registry_registration():
    assert "create_checkpoint" in TOOL_REGISTRY
    assert "rollback_checkpoint" in TOOL_REGISTRY
    assert "list_checkpoints" in TOOL_REGISTRY

    names = [t["function"]["name"] for t in raven_tools]
    assert "create_checkpoint" in names
    assert "rollback_checkpoint" in names
    assert "list_checkpoints" in names
