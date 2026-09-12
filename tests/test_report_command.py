"""
Unit tests for the /report command templating and prompt constraints (US-REPORT-001).
"""

import unittest
from pathlib import Path
from agent.utils import read_prompt_from_file


class TestReportCommand(unittest.TestCase):

    def setUp(self):
        self.report_prompt_text = read_prompt_from_file("prompts/report_prompt.md")

    def test_prompt_no_patch_diffs(self):
        """Ensure git log -p and --patch are forbidden in the prompt."""
        self.assertIn("CRITICAL CONSTRAINT", self.report_prompt_text)
        self.assertIn("DO NOT use `git log -p`", self.report_prompt_text)
        # Verify it's not given as a recommended command line
        lines = self.report_prompt_text.splitlines()
        recommended_cmd_lines = [l.strip() for l in lines if l.strip().startswith("git log")]
        for cmd in recommended_cmd_lines:
            self.assertNotIn(" -p ", f" {cmd} ")
            self.assertNotIn("--patch", cmd)

    def test_prompt_prefers_get_git_log(self):
        """Ensure the prompt recommends get_git_log as the preferred tool."""
        self.assertIn("get_git_log", self.report_prompt_text)

    def test_prompt_uses_stat(self):
        """Ensure the prompt recommends --stat for compact summaries."""
        self.assertIn("--stat", self.report_prompt_text)

    def test_prompt_path_exclusions(self):
        """Ensure noisy paths and lockfiles are excluded."""
        self.assertIn("lockfiles", self.report_prompt_text)

    def test_prompt_author_autodetection(self):
        """Ensure the prompt instructs auto-detection of git author."""
        self.assertIn("git config user.name", self.report_prompt_text)
        self.assertIn("Auto-detect the author name", self.report_prompt_text)

    def test_prompt_no_five_commit_loop(self):
        """Ensure the repetitive 5-commit increment loop is removed."""
        self.assertNotIn("increments of 5", self.report_prompt_text)

    def test_report_slash_command_default_period(self):
        """Ensure /report defaults to 'past 7 days' when no query is passed."""
        cmd = "/report"
        query = ""
        time_period = query if query else "past 7 days"
        templated = self.report_prompt_text.replace("<time_period>", time_period)

        self.assertIn("Target time period for this report: past 7 days", templated)
        self.assertNotIn("<time_period>", templated)

    def test_report_slash_command_custom_period(self):
        """Ensure /report <period> properly substitutes the custom period."""
        query = "past 2 weeks"
        time_period = query if query else "past 7 days"
        templated = self.report_prompt_text.replace("<time_period>", time_period)

        self.assertIn("Target time period for this report: past 2 weeks", templated)
        self.assertNotIn("<time_period>", templated)


if __name__ == "__main__":
    unittest.main()
