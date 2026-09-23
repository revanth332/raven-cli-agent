import ast
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VerificationResult:
    status: str  # "passed", "failed", "skipped"
    checker: str
    details: str
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.status != "failed"


def verify_python(content: str, filename: str = "file.py") -> VerificationResult:
    """Verifies Python syntax in-process using Python's AST parser."""
    try:
        ast.parse(content, filename=filename)
        return VerificationResult(
            status="passed",
            checker="python_ast",
            details="Syntax valid",
        )
    except SyntaxError as e:
        line_info = f"line {e.lineno}" if e.lineno else "unknown line"
        col_info = f"column {e.offset}" if e.offset else ""
        location = f"{line_info}, {col_info}".strip(", ")
        snippet = f" -> {e.text.strip()}" if e.text else ""
        error_msg = f"SyntaxError ({location}): {e.msg}{snippet}"
        return VerificationResult(
            status="failed",
            checker="python_ast",
            details=error_msg,
            error=error_msg,
        )
    except Exception as e:
        return VerificationResult(
            status="failed",
            checker="python_ast",
            details=f"Parse error: {e}",
            error=str(e),
        )


def verify_json(content: str) -> VerificationResult:
    """Verifies JSON formatting in-process using standard json decoder."""
    if not content.strip():
        return VerificationResult(
            status="passed",
            checker="json_parser",
            details="Empty JSON file",
        )
    try:
        json.loads(content)
        return VerificationResult(
            status="passed",
            checker="json_parser",
            details="Valid JSON format",
        )
    except json.JSONDecodeError as e:
        error_msg = f"JSONDecodeError (line {e.lineno}, col {e.colno}): {e.msg}"
        return VerificationResult(
            status="failed",
            checker="json_parser",
            details=error_msg,
            error=error_msg,
        )


def verify_toml(content: str) -> VerificationResult:
    """Verifies TOML formatting using tomllib (Python 3.11+) if available."""
    try:
        import tomllib
        tomllib.loads(content)
        return VerificationResult(
            status="passed",
            checker="toml_parser",
            details="Valid TOML format",
        )
    except ImportError:
        return VerificationResult(
            status="skipped",
            checker="toml_parser",
            details="tomllib not available",
        )
    except Exception as e:
        return VerificationResult(
            status="failed",
            checker="toml_parser",
            details=f"TOML error: {e}",
            error=str(e),
        )


def check_balanced_delimiters(content: str) -> Optional[str]:
    """
    Fast delimiter balance checker for JS/TS/JSX code.
    Skips single-line/multi-line comments and strings.
    """
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    openers = set(pairs.values())
    closers = set(pairs.keys())

    i = 0
    length = len(content)
    line_no = 1

    while i < length:
        ch = content[i]
        if ch == '\n':
            line_no += 1
            i += 1
            continue

        # Skip line comments //
        if ch == '/' and i + 1 < length and content[i + 1] == '/':
            i += 2
            while i < length and content[i] != '\n':
                i += 1
            continue

        # Skip block comments /* ... */
        if ch == '/' and i + 1 < length and content[i + 1] == '*':
            i += 2
            while i + 1 < length and not (content[i] == '*' and content[i + 1] == '/'):
                if content[i] == '\n':
                    line_no += 1
                i += 1
            i += 2
            continue

        # Skip strings ("...", '...', `...`)
        if ch in ('"', "'", '`'):
            quote = ch
            i += 1
            while i < length:
                if content[i] == '\\':
                    i += 2
                    continue
                if content[i] == '\n' and quote != '`':
                    break
                if content[i] == '\n':
                    line_no += 1
                if content[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        # Delimiter tracking
        if ch in openers:
            stack.append((ch, line_no))
        elif ch in closers:
            expected = pairs[ch]
            if not stack:
                return f"Unmatched closing '{ch}' at line {line_no}"
            top_char, top_line = stack.pop()
            if top_char != expected:
                return f"Mismatched closing '{ch}' at line {line_no} (expected closing for '{top_char}' from line {top_line})"

        i += 1

    if stack:
        unclosed_char, unclosed_line = stack[-1]
        return f"Unclosed '{unclosed_char}' opened at line {unclosed_line}"

    return None


def verify_javascript_node(file_path: Path) -> Optional[VerificationResult]:
    """Runs `node --check <file>` if Node is installed."""
    node_bin = shutil.which("node")
    if not node_bin:
        return None

    try:
        res = subprocess.run(
            [node_bin, "--check", str(file_path)],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res.returncode == 0:
            return VerificationResult(
                status="passed",
                checker="node_check",
                details="Node.js syntax valid",
            )
        else:
            err_output = res.stderr.strip() or res.stdout.strip()
            # Clean up long stack traces, extract first 3 lines
            err_lines = [l for l in err_output.splitlines() if l.strip()][:3]
            clean_err = "\n".join(err_lines)
            return VerificationResult(
                status="failed",
                checker="node_check",
                details=f"JavaScript Syntax Error:\n{clean_err}",
                error=clean_err,
            )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            status="skipped",
            checker="node_check",
            details="Node syntax check timed out (>1500ms)",
        )
    except Exception:
        return None


def run_post_edit_hooks(file_path: str | Path, content: Optional[str] = None) -> VerificationResult:
    """
    Executes automated syntax and structure verification hooks on a modified file.
    Args:
        file_path: Path to the target file.
        content: Optional in-memory content of the file. If None, reads from disk.
    Returns:
        VerificationResult detailing status, checker name, and any errors.
    """
    path = Path(file_path)
    if content is None:
        try:
            if not path.exists() or not path.is_file():
                return VerificationResult(status="skipped", checker="none", details="File does not exist")
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return VerificationResult(status="skipped", checker="none", details=f"Cannot read file: {e}")

    ext = path.suffix.lower()

    # 1. Python verification
    if ext in (".py", ".pyi", ".pyw"):
        return verify_python(content, filename=str(file_path))

    # 2. JSON verification
    if ext in (".json", ".jsonc"):
        return verify_json(content)

    # 3. TOML verification
    if ext == ".toml":
        return verify_toml(content)

    # 4. JavaScript verification (.js, .cjs, .mjs)
    if ext in (".js", ".cjs", ".mjs"):
        if path.exists():
            node_res = verify_javascript_node(path)
            if node_res is not None:
                return node_res

        # Fallback to in-process bracket check if node is not available
        bracket_err = check_balanced_delimiters(content)
        if bracket_err:
            return VerificationResult(
                status="failed",
                checker="bracket_balance",
                details=f"Syntax issue: {bracket_err}",
                error=bracket_err,
            )
        return VerificationResult(
            status="passed",
            checker="bracket_balance",
            details="Delimiters balanced",
        )

    # 5. TypeScript / React JSX / TSX (.ts, .tsx, .jsx)
    if ext in (".ts", ".tsx", ".jsx"):
        bracket_err = check_balanced_delimiters(content)
        if bracket_err:
            return VerificationResult(
                status="failed",
                checker="bracket_balance",
                details=f"Syntax issue: {bracket_err}",
                error=bracket_err,
            )
        return VerificationResult(
            status="passed",
            checker="bracket_balance",
            details="Delimiters balanced",
        )

    return VerificationResult(
        status="skipped",
        checker="none",
        details="No syntax checker configured for this file type",
    )


def format_verification_feedback(result: VerificationResult) -> str:
    """Formats verification output for inclusion in tool observation results."""
    if result.status == "passed":
        return f"[Verification: passed ({result.checker})]"
    elif result.status == "failed":
        return (
            f"[SYNTAX VERIFICATION WARNING]\n"
            f"Checker: {result.checker}\n"
            f"Details: {result.details}\n"
            f"Please review and fix this syntax issue if unintended."
        )
    return ""
