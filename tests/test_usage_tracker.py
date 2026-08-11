"""
Unit tests for pricing calculations, token counting, usage tracking, and persistence.
"""

import unittest
import tempfile
from pathlib import Path

from agent.core.pricing import get_model_pricing, calculate_cost
from agent.core.token_counter import count_tokens
from agent.core.usage_tracker import UsageTracker


class TestUsageTracker(unittest.TestCase):

    def test_model_pricing_lookup(self):
        gpt4o = get_model_pricing("gpt-4o")
        self.assertEqual(gpt4o["input_cost_per_1m"], 2.5)
        self.assertEqual(gpt4o["output_cost_per_1m"], 10.0)
        self.assertEqual(gpt4o["context_limit"], 128000)

        claude = get_model_pricing("claude-3-5-sonnet")
        self.assertEqual(claude["input_cost_per_1m"], 3.0)

        unknown = get_model_pricing("unknown-custom-model")
        self.assertIn("context_limit", unknown)

    def test_calculate_cost(self):
        # 1M prompt tokens for gpt-4o = $2.50, 1M completion tokens = $10.00 => $12.50
        cost = calculate_cost(1_000_000, 1_000_000, "gpt-4o")
        self.assertEqual(cost, 12.5)

        # 1,000 prompt tokens + 500 completion tokens for gpt-4o
        cost_small = calculate_cost(1000, 500, "gpt-4o")
        self.assertAlmostEqual(cost_small, 0.0075, places=5)

    def test_token_counter(self):
        text = "Hello world, this is a test prompt for counting tokens."
        count = count_tokens(text, "gpt-4o")
        self.assertGreater(count, 0)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a python function to add two numbers."}
        ]
        msg_count = count_tokens(messages, "gpt-4o")
        self.assertGreater(msg_count, count)

    def test_usage_tracker_record_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_file = Path(tmp_dir) / "test_usage.json"
            
            tracker = UsageTracker(persistence_file=persist_file)
            summary1 = tracker.record_turn(2000, 1000, "gpt-4o")
            
            self.assertEqual(summary1["last_prompt_tokens"], 2000)
            self.assertEqual(summary1["last_completion_tokens"], 1000)
            self.assertEqual(summary1["session_prompt_tokens"], 2000)
            self.assertEqual(summary1["total_requests"], 1)

            # Record a second turn
            summary2 = tracker.record_turn(1000, 500, "gpt-4o")
            self.assertEqual(summary2["session_prompt_tokens"], 3000)
            self.assertEqual(summary2["session_completion_tokens"], 1500)
            self.assertEqual(summary2["total_requests"], 2)

            # Test reloading from disk
            tracker2 = UsageTracker(persistence_file=persist_file)
            summary_reloaded = tracker2.get_summary("gpt-4o")
            self.assertEqual(summary_reloaded["session_prompt_tokens"], 3000)
            self.assertEqual(summary_reloaded["total_requests"], 2)


if __name__ == "__main__":
    unittest.main()
