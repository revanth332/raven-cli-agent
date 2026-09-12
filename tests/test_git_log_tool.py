"""
Unit tests for the get_git_log tool (US-REPORT-003).
"""

import unittest
from agent.tools.git_tools import get_git_log
from agent.tools.tool_registry import TOOL_REGISTRY, raven_tools


class TestGitLogTool(unittest.TestCase):

    def test_registry_integration(self):
        """Ensure get_git_log is registered in TOOL_REGISTRY and raven_tools."""
        self.assertIn("get_git_log", TOOL_REGISTRY)
        self.assertEqual(TOOL_REGISTRY["get_git_log"]["fn"], get_git_log)

        tool_names = [t["function"]["name"] for t in raven_tools if t.get("type") == "function"]
        self.assertIn("get_git_log", tool_names)

    def test_get_git_log_execution(self):
        """Verify get_git_log executes and returns commits on current git repo."""
        result = get_git_log(since="1 year ago", max_commits=5, include_stat=True)
        self.assertIsInstance(result, str)
        # In this repository, commits should be returned
        self.assertFalse(result.startswith("Failed to get git log"))

    def test_get_git_log_max_commits_limit(self):
        """Verify max_commits caps output without errors."""
        result = get_git_log(since="10 years ago", max_commits=2, include_stat=False)
        self.assertIsInstance(result, str)
        self.assertFalse(result.startswith("Failed to get git log"))

    def test_get_git_log_no_commits_found(self):
        """Verify friendly message when no commits match the timeframe."""
        result = get_git_log(since="1 second ago", author="non_existent_author_999999")
        self.assertIn("No commits found", result)


if __name__ == "__main__":
    unittest.main()
