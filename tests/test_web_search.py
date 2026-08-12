import unittest
from unittest.mock import patch, MagicMock
from agent.tools.web_tools import web_search


class TestWebSearch(unittest.TestCase):

    def test_web_search_empty_query(self):
        res = web_search("")
        self.assertEqual(len(res), 1)
        self.assertIn("error", res[0])
        self.assertIn("cannot be empty", res[0]["error"])

    @patch("agent.tools.web_tools.DDGS")
    def test_web_search_success(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs
        mock_ddgs.text.return_value = [
            {"title": "Python Docs", "href": "https://docs.python.org", "body": "Official Python Documentation"},
            {"title": "Python Package Index", "href": "https://pypi.org", "body": "PyPI packages repository"}
        ]

        res = web_search("python docs", max_results=2)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["title"], "Python Docs")
        self.assertEqual(res[0]["url"], "https://docs.python.org")
        self.assertEqual(res[0]["snippet"], "Official Python Documentation")

    @patch("agent.tools.web_tools.DDGS")
    def test_web_search_no_results(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs
        mock_ddgs.text.return_value = []

        res = web_search("xyznonexistentquery12345")
        self.assertEqual(len(res), 1)
        self.assertIn("message", res[0])
        self.assertIn("No web search results found", res[0]["message"])

    @patch("agent.tools.web_tools.DDGS")
    def test_web_search_exception(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs
        mock_ddgs.text.side_effect = Exception("Network timeout")

        res = web_search("python")
        self.assertEqual(len(res), 1)
        self.assertIn("error", res[0])
        self.assertIn("Failed to execute web search", res[0]["error"])


if __name__ == "__main__":
    unittest.main()
