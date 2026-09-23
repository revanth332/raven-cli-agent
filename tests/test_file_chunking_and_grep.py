import pytest
from pathlib import Path
from agent.tools.file_tools import read_file, search_file_content
from agent.tools.tool_registry import TOOL_REGISTRY, raven_tools


def test_read_file_basic(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("line one\nline two\nline three\n", encoding="utf-8")

    res = read_file(str(test_file))
    assert "   1 | line one" in res
    assert "   2 | line two" in res
    assert "   3 | line three" in res


def test_read_file_pagination(tmp_path):
    test_file = tmp_path / "paginated.txt"
    lines = [f"Item {i}" for i in range(1, 21)]
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Read page 1
    page1 = read_file(str(test_file), start_line=1, line_count=5)
    assert "   1 | Item 1" in page1
    assert "   5 | Item 5" in page1
    assert "Item 6" not in page1
    assert "[Showing lines 1-5 of 20. Use start_line=6 to read further]" in page1

    # Read page 2
    page2 = read_file(str(test_file), start_line=6, line_count=5)
    assert "   6 | Item 6" in page2
    assert "  10 | Item 10" in page2
    assert "[Showing lines 6-10 of 20. Use start_line=11 to read further]" in page2


def test_read_file_without_line_numbers(tmp_path):
    test_file = tmp_path / "plain.txt"
    test_file.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    res = read_file(str(test_file), include_line_numbers=False)
    assert res == "alpha\nbeta\ngamma"


def test_read_file_out_of_bounds_and_empty(tmp_path):
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    res_empty = read_file(str(empty_file))
    assert "is empty" in res_empty

    non_empty = tmp_path / "small.txt"
    non_empty.write_text("single line\n", encoding="utf-8")
    res_oob = read_file(str(non_empty), start_line=50)
    assert "exceeds total lines" in res_oob


def test_read_file_sensitive_and_not_found(tmp_path):
    assert "ACCESS DENIED" in read_file(".env")
    assert "ACCESS DENIED" in read_file("sub/.env.production")
    assert "does not exist" in read_file(str(tmp_path / "non_existent.py"))


def test_search_file_content_literal_and_regex(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code_file = tmp_path / "service.py"
    code_file.write_text(
        "import sys\n\ndef calculate_tax(amount):\n    rate = 0.15\n    return amount * rate\n\ndef run():\n    pass\n",
        encoding="utf-8"
    )

    # Search with literal string
    res_lit = search_file_content("calculate_tax")
    assert "--- service.py ---" in res_lit
    assert ">    3 | def calculate_tax(amount):" in res_lit
    assert "   2 |" in res_lit  # Context before
    assert "   4 |     rate = 0.15" in res_lit  # Context after

    # Search with regex pattern
    res_regex = search_file_content(r"rate\s*=\s*\d+\.\d+")
    assert "--- service.py ---" in res_regex
    assert ">    4 |     rate = 0.15" in res_regex


def test_search_file_content_specific_target(tmp_path):
    sub_dir = tmp_path / "nested"
    sub_dir.mkdir()
    f1 = sub_dir / "target.py"
    f1.write_text("MATCH_HERE_UNIQUE = 42\n", encoding="utf-8")

    res = search_file_content("MATCH_HERE_UNIQUE", file_path=str(f1))
    assert "MATCH_HERE_UNIQUE" in res
    assert ">    1 | MATCH_HERE_UNIQUE = 42" in res


def test_search_file_content_max_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_file = tmp_path / "test.log"
    log_file.write_text("\n".join([f"LOG_EVENT_{i}: something" for i in range(50)]), encoding="utf-8")

    res = search_file_content("LOG_EVENT", max_matches=5)
    assert "[Showing first 5 matches." in res


def test_search_file_content_sensitive_and_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res_empty = search_file_content("   ")
    assert "query cannot be empty" in res_empty

    res_sens = search_file_content("SECRET", file_path=".env")
    assert "ACCESS DENIED" in res_sens

    res_none = search_file_content("NONEXISTENT_STRING_XYZ")
    assert "No matches found" in res_none


def test_tool_registry_registration():
    assert "search_file_content" in TOOL_REGISTRY
    assert TOOL_REGISTRY["search_file_content"]["fn"] == search_file_content

    tool_names = [t["function"]["name"] for t in raven_tools]
    assert "read_file" in tool_names
    assert "search_file_content" in tool_names

    read_file_meta = next(t for t in raven_tools if t["function"]["name"] == "read_file")
    props = read_file_meta["function"]["parameters"]["properties"]
    assert "start_line" in props
    assert "line_count" in props
    assert "include_line_numbers" in props
