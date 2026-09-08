"""
Unit tests for TUI tool header truncation and diff rendering logic.
"""

import unittest
from rich.text import Text


class TestUITruncation(unittest.TestCase):

    def setUp(self):
        self.MAX_DIFF_LINES = 8
        self.MAX_ARG_LENGTH = 80

    def append_tool_header(self, tool_logs: Text, display_name: str, display_value: str = "") -> None:
        tool_logs.append("\n• ", style="bold cyan")
        tool_logs.append(display_name, style="bold cyan")
        if display_value:
            clean_val = " ".join(str(display_value).split())
            if len(clean_val) > self.MAX_ARG_LENGTH:
                clean_val = clean_val[: self.MAX_ARG_LENGTH - 3] + "..."
            tool_logs.append("(", style="dim white")
            tool_logs.append(clean_val, style="dim white")
            tool_logs.append(")", style="dim white")
        tool_logs.append("\n")

    def format_patch_diff(self, file_path: str, search_block: str, replace_block: str) -> Text:
        tool_logs = Text()
        self.append_tool_header(tool_logs, "Update", file_path)

        if search_block or replace_block:
            search_block_lines = search_block.rstrip().split("\n") if search_block else []
            replace_block_lines = replace_block.rstrip().split("\n") if replace_block else []
            search_count = len(search_block_lines)
            replace_count = len(replace_block_lines)

            tool_logs.append("   |_ Updated ", style="dim white")
            tool_logs.append(f"{file_path} ")
            tool_logs.append("with ", style="dim white")
            tool_logs.append(f"{replace_count} ", style="bold green" if replace_count else "dim white")
            tool_logs.append("addition" if replace_count == 1 else "additions", style="dim white")
            tool_logs.append(" and ", style="dim white")
            tool_logs.append(f"{search_count} ", style="bold red" if search_count else "dim white")
            tool_logs.append("removal\n" if search_count == 1 else "removals\n", style="dim white")

            if search_block_lines:
                visible_search = search_block_lines[: self.MAX_DIFF_LINES]
                for line in visible_search:
                    tool_logs.append("       ")
                    tool_logs.append(f"- {line}\n", style="white on #961b1b")
                collapsed_search = search_count - len(visible_search)
                if collapsed_search > 0:
                    tool_logs.append(f"       ... [{collapsed_search} search lines collapsed]\n", style="dim italic white")

            if replace_block_lines:
                visible_replace = replace_block_lines[: self.MAX_DIFF_LINES]
                for line in visible_replace:
                    tool_logs.append("       ")
                    tool_logs.append(f"+ {line}\n", style="white on #26753a")
                collapsed_replace = replace_count - len(visible_replace)
                if collapsed_replace > 0:
                    tool_logs.append(f"       ... [{collapsed_replace} replace lines collapsed]\n", style="dim italic white")

        return tool_logs

    def test_short_argument_no_truncation(self):
        logs = Text()
        self.append_tool_header(logs, "Read", "short_file.py")
        plain = logs.plain
        self.assertIn("• Read(short_file.py)", plain)
        self.assertNotIn("...", plain)

    def test_long_argument_truncated_with_ellipsis(self):
        logs = Text()
        long_arg = "a" * 120
        self.append_tool_header(logs, "Execute", long_arg)
        plain = logs.plain
        expected_len_arg = self.MAX_ARG_LENGTH - 3
        self.assertIn("• Execute(" + "a" * expected_len_arg + "...)", plain)

    def test_multiline_argument_whitespace_normalized(self):
        logs = Text()
        multiline_arg = "line1\n   line2\n\t  line3"
        self.append_tool_header(logs, "Command", multiline_arg)
        plain = logs.plain
        self.assertIn("• Command(line1 line2 line3)", plain)

    def test_diff_truncation_under_limit(self):
        search = "line1\nline2\nline3"
        replace = "newline1\nnewline2"
        logs = self.format_patch_diff("agent/test.py", search, replace)
        plain = logs.plain

        self.assertIn("Updated agent/test.py with 2 additions and 3 removals", plain)
        self.assertIn("- line1", plain)
        self.assertIn("- line2", plain)
        self.assertIn("- line3", plain)
        self.assertIn("+ newline1", plain)
        self.assertIn("+ newline2", plain)
        self.assertNotIn("collapsed", plain)

    def test_diff_truncation_over_limit(self):
        search = "\n".join([f"old_line_{i}" for i in range(15)])
        replace = "\n".join([f"new_line_{i}" for i in range(12)])
        logs = self.format_patch_diff("agent/large.py", search, replace)
        plain = logs.plain

        self.assertIn("Updated agent/large.py with 12 additions and 15 removals", plain)
        self.assertIn("- old_line_7", plain)
        self.assertNotIn("- old_line_8", plain)
        self.assertIn("... [7 search lines collapsed]", plain)

        self.assertIn("+ new_line_7", plain)
        self.assertNotIn("+ new_line_8", plain)
        self.assertIn("... [4 replace lines collapsed]", plain)

    def test_singular_plural_grammar(self):
        # 1 addition and 1 removal
        logs = self.format_patch_diff("agent/single.py", "remove_me", "add_me")
        plain = logs.plain
        self.assertIn("1 addition and 1 removal", plain)

        # 2 additions and 0 removals
        logs_add_only = self.format_patch_diff("agent/add.py", "", "line1\nline2")
        plain_add_only = logs_add_only.plain
        self.assertIn("2 additions and 0 removals", plain_add_only)


if __name__ == "__main__":
    unittest.main()
