"""
Unit tests for command output truncation and safety guards (US-REPORT-002).
"""

import unittest
from agent.tools.miscellaneous_tools import (
    truncate_output,
    execute_command,
    MAX_COMMAND_OUTPUT_CHARS,
    MAX_COMMAND_OUTPUT_LINES,
)


class TestCommandTruncation(unittest.TestCase):

    def test_short_output_not_truncated(self):
        """Output well within limits should be returned untouched."""
        short_text = "Line 1\nLine 2\nLine 3\n"
        result = truncate_output(short_text, max_chars=1000, max_lines=10)
        self.assertEqual(result, short_text)

    def test_empty_output(self):
        """Empty or falsy text should return as-is."""
        self.assertEqual(truncate_output(""), "")
        self.assertEqual(truncate_output(None), None)

    def test_line_limit_truncation(self):
        """Output exceeding max_lines should preserve head and tail and add banner."""
        lines = [f"Commit line {i}: details about work done" for i in range(200)]
        text = "\n".join(lines)

        result = truncate_output(text, max_chars=50000, max_lines=100)
        self.assertIn("Output truncated", result)
        self.assertIn("lines", result)
        self.assertIn("characters omitted", result)

        # Head lines should be preserved
        self.assertIn("Commit line 0:", result)
        self.assertIn("Commit line 70:", result)

        # Tail lines should be preserved
        self.assertIn("Commit line 199:", result)

        # Middle lines should have been omitted
        self.assertNotIn("Commit line 100:", result)

    def test_character_limit_truncation(self):
        """A single line exceeding max_chars should be truncated."""
        long_line = "A" * 10000
        result = truncate_output(long_line, max_chars=2000, max_lines=50)

        self.assertIn("Output truncated", result)
        self.assertLessEqual(len(result), 2500)  # Capped close to max_chars + banner
        self.assertTrue(result.startswith("A" * 500))
        self.assertTrue(result.endswith("A" * 200))

    def test_execute_command_exit_code_preserved(self):
        """execute_command must always include the Exit Code."""
        res = execute_command('python -c "import sys; sys.exit(42)"')
        self.assertIn("Exit Code: 42", res)

    def test_execute_command_truncation_end_to_end(self):
        """End-to-end execute_command with large stdout must cap output."""
        cmd = 'python -c "for i in range(300): print(f\'commit_hash_{i} test commit\')"'
        res = execute_command(cmd)

        self.assertIn("Exit Code: 0", res)
        self.assertIn("STDOUT:", res)
        self.assertIn("Output truncated", res)
        self.assertIn("commit_hash_0", res)
        self.assertIn("commit_hash_299", res)
        self.assertNotIn("commit_hash_150", res)

    def test_execute_command_stderr_truncation(self):
        """execute_command with large stderr must also be capped."""
        cmd = 'python -c "import sys; [sys.stderr.write(f\'err line {i}\\n\') for i in range(200)]"'
        res = execute_command(cmd)

        self.assertIn("STDERR:", res)
        self.assertIn("Output truncated", res)
        self.assertIn("err line 0", res)
        self.assertIn("err line 199", res)


if __name__ == "__main__":
    unittest.main()
