import sys
from pathlib import Path

# Add project root to path to ensure we can import agent modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.core.safety import is_command_dangerous

def test_safe_commands():
    safe_commands = [
        "git status",
        "pytest",
        "npm run build",
        "echo hello",
        "dir",
        "ls -la",
        "git diff",
        "git add .",
        "python testing.py",
        "python -m pip install -r requirements.txt",
        "mkdir temp_dir",
        "type README.md",
        "cat README.md",
        "git commit -m \"initial commit\"",
    ]
    for cmd in safe_commands:
        assert not is_command_dangerous(cmd), f"Expected '{cmd}' to be SAFE, but it was classified as DANGEROUS."

def test_dangerous_commands():
    dangerous_commands = [
        "rm -rf node_modules",
        "del /s /q temp",
        "git rm -r src/",
        "rmdir /s /q build",
        "dd if=/dev/zero of=/dev/sda",
        "fdisk /dev/sda",
        "chmod 777 secret.key",
        "chown root secret.key",
        "shred -u confidential.txt",
        "wipe -rf docs/",
        "format c:",
        "mkfs.ext4 /dev/sdb1",
    ]
    for cmd in dangerous_commands:
        assert is_command_dangerous(cmd), f"Expected '{cmd}' to be DANGEROUS, but it was classified as SAFE."

def test_chained_commands():
    chained_dangerous = [
        "echo 'starting...' && rm -rf temp",
        "git status; rm -f data.txt",
        "pytest || rm -rf reports",
        "ls | grep txt && rm -rf list.txt",
    ]
    for cmd in chained_dangerous:
        assert is_command_dangerous(cmd), f"Expected chained command '{cmd}' to be DANGEROUS, but it was classified as SAFE."

def test_fail_safe_parsing_error():
    # Unbalanced quotes should cause a parsing error and fail-safe to True (dangerous)
    bad_cmd = "rm -rf \"unclosed quote"
    assert is_command_dangerous(bad_cmd), f"Expected unbalanced quote command '{bad_cmd}' to fail-safe to DANGEROUS, but was SAFE."

if __name__ == "__main__":
    print("Running safety checks tests...")
    try:
        test_safe_commands()
        print("[OK] All safe commands correctly classified.")
        test_dangerous_commands()
        print("[OK] All dangerous commands correctly classified.")
        test_chained_commands()
        print("[OK] Chained commands correctly checked.")
        test_fail_safe_parsing_error()
        print("[OK] Fail-safe unbalanced quotes checked.")
        print("\nAll Tests Passed Successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nAssertion Error: {e}")
        sys.exit(1)
