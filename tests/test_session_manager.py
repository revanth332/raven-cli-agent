"""
Unit tests for session_manager persistence and CRUD operations.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from agent.core import session_manager


class TestSessionManager(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.orig_get_dir = session_manager.get_sessions_dir
        session_manager.get_sessions_dir = lambda: self.tmp_dir

    def tearDown(self):
        session_manager.get_sessions_dir = self.orig_get_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_and_load_session(self):
        sess = session_manager.create_session(model_name="gpt-4o", title="Test Conversation")
        sess["messages"].append({"role": "user", "content": "hello world"})
        session_manager.save_session(sess)

        self.assertIsNotNone(sess["session_id"])
        self.assertEqual(sess["title"], "Test Conversation")

        loaded = session_manager.load_session(sess["session_id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["session_id"], sess["session_id"])
        self.assertEqual(loaded["title"], "Test Conversation")

    def test_list_sessions_sorting(self):
        s1 = session_manager.create_session(title="Session 1")
        s2 = session_manager.create_session(title="Session 2")

        s1["messages"].append({"role": "user", "content": "hello from s1"})
        s2["messages"].append({"role": "user", "content": "hello from s2"})
        session_manager.save_session(s1)
        session_manager.save_session(s2)

        sessions = session_manager.list_sessions()
        self.assertEqual(len(sessions), 2)
        # Most recently saved session s2 should be first
        self.assertEqual(sessions[0]["session_id"], s2["session_id"])

    def test_delete_session(self):
        sess = session_manager.create_session(title="Session to Delete")
        sess["messages"].append({"role": "user", "content": "delete me"})
        session_manager.save_session(sess)
        sid = sess["session_id"]
        
        self.assertTrue(session_manager.delete_session(sid))
        self.assertIsNone(session_manager.load_session(sid))


if __name__ == "__main__":
    unittest.main()
