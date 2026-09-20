import unittest
from unittest.mock import patch, MagicMock

from agent.core.indexer import search_codebase, index_project, get_vector_db, GeminiEmbeddingFunction
from agent.tools.memory_tools import recall_memory, index_episodic_memory, get_episodic_vector_db


class TestEmbeddingModelRequirement(unittest.TestCase):

    def test_search_codebase_disabled_when_no_embedding_model(self):
        """search_codebase must return 'Tool is not supported.' if no embedding model is configured."""
        with patch("agent.core.indexer.settings.RAVEN_EMBEDDING_MODEL", None):
            with patch("agent.core.indexer.settings.EMBEDDING_MODEL", None):
                with patch("agent.core.indexer.use_vertex_ai", return_value=True):
                    result = search_codebase("search query")
                    self.assertEqual(result, "Tool is not supported.")

    def test_recall_memory_disabled_when_no_embedding_model(self):
        """recall_memory must return 'Tool is not supported.' if no embedding model is configured."""
        with patch("agent.tools.memory_tools.settings.RAVEN_EMBEDDING_MODEL", None):
            with patch("agent.tools.memory_tools.settings.EMBEDDING_MODEL", None):
                with patch("agent.tools.memory_tools.use_vertex_ai", return_value=True):
                    result = recall_memory("memory query")
                    self.assertEqual(result, "Tool is not supported.")

    def test_indexing_helpers_disabled_when_no_embedding_model(self):
        """index_project, index_episodic_memory, and db getters must return early/None if no embedding model."""
        with patch("agent.core.indexer.settings.RAVEN_EMBEDDING_MODEL", None):
            with patch("agent.core.indexer.settings.EMBEDDING_MODEL", None):
                with patch("agent.core.indexer.use_vertex_ai", return_value=True):
                    self.assertIn("No embedding model configured", index_project())
                    self.assertIsNone(get_vector_db())

        with patch("agent.tools.memory_tools.settings.RAVEN_EMBEDDING_MODEL", None):
            with patch("agent.tools.memory_tools.settings.EMBEDDING_MODEL", None):
                with patch("agent.tools.memory_tools.use_vertex_ai", return_value=True):
                    self.assertIsNone(get_episodic_vector_db())
                    # Should return safely without error
                    index_episodic_memory()

    @patch("agent.core.indexer.get_vector_db")
    @patch("agent.core.indexer.index_project")
    def test_search_codebase_enabled_when_embedding_model_configured(self, mock_index, mock_get_db):
        """search_codebase queries collection when embedding model and vertex ai are configured."""
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["def foo(): pass"]],
            "metadatas": [[{"file_path": "foo.py", "type": "function", "name": "foo"}]]
        }
        mock_get_db.return_value = mock_col

        with patch("agent.core.indexer.settings.RAVEN_EMBEDDING_MODEL", "text-embedding-005"):
            with patch("agent.core.indexer.use_vertex_ai", return_value=True):
                result = search_codebase("foo function")
                self.assertIn("File: foo.py", result)
                self.assertIn("def foo(): pass", result)


if __name__ == "__main__":
    unittest.main()
