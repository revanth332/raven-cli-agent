import unittest
from agent.core.loop_guard import LoopGuard, LoopGuardState


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

    def test_soft_limit_enters_wrap_up_before_finalization(self):
        for _ in range(5):
            self.guard.increment_turn()

        self.assertEqual(self.guard.get_state(), LoopGuardState.WRAP_UP)
        self.assertFalse(self.guard.is_turn_limit_reached())
        self.assertIn("wrap up", self.guard.get_wrap_up_instruction())

        self.guard.increment_turn()
        self.assertEqual(self.guard.get_state(), LoopGuardState.WRAP_UP)
        self.guard.increment_turn()
        self.assertEqual(self.guard.get_state(), LoopGuardState.FINALIZE)
        self.assertTrue(self.guard.is_turn_limit_reached())

    def test_hard_turn_limit_forces_finalization(self):
        guard = LoopGuard(max_turns=5, hard_max_turns=6, grace_turns=10)
        for _ in range(6):
            guard.increment_turn()
        self.assertEqual(guard.get_state(), LoopGuardState.FINALIZE)

    def test_tool_call_limit_forces_finalization(self):
        guard = LoopGuard(max_turns=10, max_tool_calls=3)
        guard.record_tool_call(3)
        self.assertEqual(guard.get_state(), LoopGuardState.FINALIZE)

    def test_no_progress_limit_forces_finalization_and_progress_resets_it(self):
        guard = LoopGuard(max_no_progress_rounds=3)
        guard.record_round_outcome(False)
        guard.record_round_outcome(False)
        guard.record_round_outcome(True)
        self.assertEqual(guard.no_progress_rounds, 0)

        for _ in range(3):
            guard.record_round_outcome(False)
        self.assertEqual(guard.get_state(), LoopGuardState.FINALIZE)

    def test_result_progress_detection(self):
        self.assertFalse(self.guard.result_made_progress("Error: command failed"))
        self.assertFalse(self.guard.result_made_progress({"success": False, "error": "missing"}))
        self.assertTrue(self.guard.result_made_progress({"success": True}))
        self.assertTrue(self.guard.result_made_progress("file updated"))

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
        self.assertEqual(self.guard.tool_call_count, 0)
        self.assertEqual(self.guard.no_progress_rounds, 0)
        self.assertIsNone(self.guard.wrap_up_started_at)
        is_dup, _ = self.guard.check_duplicate("execute_command", {"command": "dir"})
        self.assertFalse(is_dup)


if __name__ == "__main__":
    unittest.main()
