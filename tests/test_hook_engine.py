import pytest
from pathlib import Path
from agent.core.hook_engine import (
    run_post_edit_hooks,
    verify_python,
    verify_json,
    check_balanced_delimiters,
    format_verification_feedback,
)
from agent.tools.file_tools import create_file, patch_file


def test_verify_python_valid():
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = verify_python(code, filename="math_util.py")
    assert res.status == "passed"
    assert res.checker == "python_ast"
    assert res.is_valid is True


def test_verify_python_syntax_error():
    broken_code = "def add(a, b:\n    return a + b\n"
    res = verify_python(broken_code, filename="bad.py")
    assert res.status == "failed"
    assert res.checker == "python_ast"
    assert "SyntaxError" in res.details
    assert res.is_valid is False


def test_verify_json_valid_and_invalid():
    valid_json = '{"name": "raven", "enabled": true, "version": 1}'
    res_valid = verify_json(valid_json)
    assert res_valid.status == "passed"
    assert res_valid.checker == "json_parser"

    invalid_json = '{"name": "raven", "trailing": true,}'
    res_invalid = verify_json(invalid_json)
    assert res_invalid.status == "failed"
    assert "JSONDecodeError" in res_invalid.details


def test_check_balanced_delimiters():
    # Valid JS / TS snippet with strings and comments containing braces
    valid_js = """
    // Here is a comment with { unbalanced ( braces
    /* Block comment [ { ( */
    function greet(name) {
        const msg = `Hello {${name}} [bracket in string]`;
        const items = ["alpha", "beta"];
        return { message: msg, count: items.length };
    }
    """
    assert check_balanced_delimiters(valid_js) is None

    # Invalid JS snippet with unclosed curly brace
    broken_js = "function test() { const x = [1, 2];"
    err = check_balanced_delimiters(broken_js)
    assert err is not None
    assert "Unclosed '{'" in err

    # Mismatched closing delimiter
    mismatched_js = "function test() { return [1, 2}; }"
    err_mismatched = check_balanced_delimiters(mismatched_js)
    assert err_mismatched is not None
    assert "Mismatched" in err_mismatched or "Unmatched" in err_mismatched


def test_run_post_edit_hooks_unsupported_extension():
    res = run_post_edit_hooks("readme.md", content="# Hello World")
    assert res.status == "skipped"


def test_create_file_integration_with_hooks(tmp_path):
    py_file = tmp_path / "valid.py"
    res = create_file(str(py_file), content="x = 10\ny = 20\n")
    assert "Successfully created file" in res
    assert "[Verification: passed (python_ast)]" in res


def test_patch_file_integration_with_syntax_warning(tmp_path):
    py_file = tmp_path / "app.py"
    py_file.write_text("def run():\n    print('start')\n    print('finish')\n", encoding="utf-8")

    # Patch with a syntax error (broken colon/parenthesis)
    patch_res = patch_file(
        str(py_file),
        search_block="    print('start')",
        replace_block="    if True print('start')"  # Missing colon in Python
    )

    assert "Successfully updated" in patch_res
    assert "[SYNTAX VERIFICATION WARNING]" in patch_res
    assert "python_ast" in patch_res
    assert "SyntaxError" in patch_res
