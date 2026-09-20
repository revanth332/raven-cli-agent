import unittest
from agent.core.loop_guard import LoopGuard


class TestLoopGuard(unittest.TestCase):
    def setUp(self):
        self.guard = LoopGuard(max_turns=5, history_window=3)

    def test_initial_state(self):
        self.assertEqual(self.guard.turn_count, 0)
        self.assertFalse(self.guard.is_turn_limit_reached())

    def test_different_calls_not_duplicate(self):
        is_dup, _ = self.guard.check_duplicate("get_git_status", {})
        self.assertFalse(is_dup)
        self.guard.record_call("get_git_status", {})

        is_dup2, _ = self.guard.check_duplicate("read_file", {"file_path": "a.py"})
        self.assertFalse(is_dup2)
        self.guard.record_call("read_file", {"file_path": "a.py"})

    def test_consecutive_duplicate_call_detected(self):
        self.guard.record_call("get_git_diff", {"file_path": "agent/app.py"})
        
        is_dup, msg = self.guard.check_duplicate("get_git_diff", {"file_path": "agent/app.py"})
        self.assertTrue(is_dup)
        self.assertIn("Duplicate tool call intercepted", msg)
        self.assertIn("get_git_diff", msg)

    def test_duplicate_detection_key_order_invariant(self):
        # Dict with different key orders should still match
        self.guard.record_call("patch_file", {"file_path": "test.txt", "search_block": "foo", "replace_block": "bar"})

        is_dup, _ = self.guard.check_duplicate("patch_file", {"replace_block": "bar", "search_block": "foo", "file_path": "test.txt"})
        self.assertTrue(is_dup)

    def test_turn_ceiling_enforcement(self):
        for _ in range(5):
            self.assertFalse(self.guard.is_turn_limit_reached())
            self.guard.increment_turn()

        self.assertTrue(self.guard.is_turn_limit_reached())
        self.assertIn("reached maximum of 5", self.guard.get_limit_warning())

    def test_sliding_window_expiration(self):
        guard = LoopGuard(max_turns=10, history_window=2)
        guard.record_call("read_file", {"file_path": "initial.txt"})
        guard.record_call("read_file", {"file_path": "second.txt"})
        guard.record_call("read_file", {"file_path": "third.txt"})

        # "initial.txt" is outside window of 2, so should not be marked duplicate
        is_dup, _ = guard.check_duplicate("read_file", {"file_path": "initial.txt"})
        self.assertFalse(is_dup)

    def test_reset(self):
        self.guard.record_call("execute_command", {"command": "dir"})
        self.guard.increment_turn()
        self.guard.reset()

        self.assertEqual(self.guard.turn_count, 0)
        is_dup, _ = self.guard.check_duplicate("execute_command", {"command": "dir"})
        self.assertFalse(is_dup)


if __name__ == "__main__":
    unittest.main()
