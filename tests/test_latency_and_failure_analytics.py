"""
Unit and integration tests for Model Latency & Failure Analytics Dashboard Enhancement.
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.core.usage_tracker import UsageTracker, compute_percentile
from agent.core.llm import extract_error_code, AgentChatSession


class TestLatencyAndFailureAnalytics(unittest.TestCase):

    def test_compute_percentile(self):
        # Empty samples
        self.assertEqual(compute_percentile([], 0.5), 0.0)

        # Single sample
        self.assertEqual(compute_percentile([450.0], 0.5), 450.0)
        self.assertEqual(compute_percentile([450.0], 0.95), 450.0)

        # Known sample set: [620, 640, 710, 850, 1200]
        samples = sorted([620, 710, 850, 1200, 640])
        p50 = compute_percentile(samples, 0.50)
        p95 = compute_percentile(samples, 0.95)

        self.assertEqual(p50, 710.0)
        # 850 + 0.8 * 350 = 1130.0
        self.assertEqual(p95, 1130.0)

        # 100 samples from 1 to 100
        samples_100 = list(range(1, 101))
        p50_100 = compute_percentile(samples_100, 0.50)
        p95_100 = compute_percentile(samples_100, 0.95)
        self.assertEqual(p50_100, 50.5)
        self.assertEqual(p95_100, 95.0)

    def test_extract_error_code(self):
        # Rate limit status
        e_429 = Exception("Rate limit exceeded")
        setattr(e_429, "status_code", 429)
        self.assertEqual(extract_error_code(e_429), "429")

        # Rate limit in text
        e_quota = Exception("Resource has been exhausted (quota / rate limit)")
        self.assertEqual(extract_error_code(e_quota), "429")

        # Timeout
        e_timeout = Exception("Request timed out after 30s")
        self.assertEqual(extract_error_code(e_timeout), "TIMEOUT")

        # Context exceeded
        e_ctx = Exception("This model's maximum context length is 128000 tokens. However, your request resulted in 130000 tokens.")
        self.assertEqual(extract_error_code(e_ctx), "CONTEXT_EXCEEDED")

        # Auth
        e_auth = Exception("Invalid API key provided")
        setattr(e_auth, "status_code", 401)
        self.assertEqual(extract_error_code(e_auth), "AUTH_ERROR")

        # Server error 503
        e_503 = Exception("Service unavailable")
        setattr(e_503, "status_code", 503)
        self.assertEqual(extract_error_code(e_503), "503")

        # Server error 500
        e_500 = Exception("Internal server error")
        setattr(e_500, "status_code", 500)
        self.assertEqual(extract_error_code(e_500), "500")

    def test_record_turn_success_and_latency_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_file = Path(tmp_dir) / "usage_history.json"
            tracker = UsageTracker(persistence_file=persist_file)

            # Record 3 successful turns
            tracker.record_turn(1000, 200, "gpt-4o", duration_ms=500.0, ttft_ms=150.0, status="success")
            tracker.record_turn(1500, 300, "gpt-4o", duration_ms=700.0, ttft_ms=200.0, status="success")
            summary = tracker.record_turn(800, 100, "gpt-4o", duration_ms=600.0, ttft_ms=160.0, status="success")

            self.assertEqual(summary["total_requests"], 3)
            self.assertEqual(summary["last_duration_ms"], 600.0)
            self.assertEqual(summary["last_ttft_ms"], 160.0)

            # Check daily structure
            today = list(tracker.daily_usage.keys())[0]
            model_data = tracker.daily_usage[today]["gpt-4o"]

            self.assertEqual(model_data["requests"], 3)
            self.assertEqual(model_data["reliability"]["success_count"], 3)
            self.assertEqual(model_data["reliability"]["failure_count"], 0)
            self.assertEqual(len(model_data["latency"]["samples_ms"]), 3)
            self.assertEqual(model_data["latency"]["p50_ms"], 600.0)
            self.assertEqual(model_data["latency"]["avg_ms"], 600.0)
            self.assertEqual(model_data["latency"]["avg_ttft_ms"], 170.0)
            self.assertEqual(len(model_data["latency"]["points"]), 3)

    def test_record_turn_failure_and_zero_tokens(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_file = Path(tmp_dir) / "usage_history.json"
            tracker = UsageTracker(persistence_file=persist_file)

            # Record a failed turn (e.g. rate limit 429 with 0 tokens)
            tracker.record_turn(
                prompt_tokens=0,
                completion_tokens=0,
                model_name="claude-3-5-sonnet",
                duration_ms=250.0,
                ttft_ms=None,
                status="error",
                error_code="429"
            )

            today = list(tracker.daily_usage.keys())[0]
            model_data = tracker.daily_usage[today]["claude-3-5-sonnet"]

            self.assertEqual(model_data["requests"], 1)
            self.assertEqual(model_data["prompt_tokens"], 0)
            self.assertEqual(model_data["completion_tokens"], 0)
            self.assertEqual(model_data["cost"], 0.0)
            self.assertEqual(model_data["reliability"]["success_count"], 0)
            self.assertEqual(model_data["reliability"]["failure_count"], 1)
            self.assertEqual(model_data["reliability"]["failure_reasons"]["429"], 1)

    def test_legacy_history_backward_compatibility(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_file = Path(tmp_dir) / "usage_history.json"

            # Create legacy JSON without latency/reliability keys
            legacy_data = {
                "session_prompt_tokens": 5000,
                "session_completion_tokens": 1200,
                "session_cost": 0.0245,
                "total_requests": 4,
                "daily_usage": {
                    "2025-05-01": {
                        "gpt-4o": {
                            "prompt_tokens": 5000,
                            "completion_tokens": 1200,
                            "tokens": 6200,
                            "requests": 4,
                            "cost": 0.0245
                        }
                    }
                }
            }
            with open(persist_file, "w", encoding="utf-8") as f:
                json.dump(legacy_data, f)

            # Load via UsageTracker
            tracker = UsageTracker(persistence_file=persist_file)
            day_rec = tracker.daily_usage["2025-05-01"]["gpt-4o"]

            # Must have defaulted structures
            self.assertIn("latency", day_rec)
            self.assertEqual(day_rec["latency"]["avg_ms"], 0.0)
            self.assertEqual(day_rec["latency"]["p50_ms"], 0.0)
            self.assertEqual(day_rec["latency"]["samples_ms"], [])

            self.assertIn("reliability", day_rec)
            self.assertEqual(day_rec["reliability"]["success_count"], 4)
            self.assertEqual(day_rec["reliability"]["failure_count"], 0)

            # Record a new turn on top of legacy data
            tracker.record_turn(100, 50, "gpt-4o", duration_ms=400.0, status="success")
            self.assertEqual(tracker.total_requests, 5)

    def test_dashboard_files_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_file = Path(tmp_dir) / "usage_history.json"
            tracker = UsageTracker(persistence_file=persist_file)

            tracker.record_turn(500, 100, "gemini-2.5-flash", duration_ms=300.0, ttft_ms=100.0)
            tracker.record_turn(0, 0, "gemini-2.5-flash", duration_ms=120.0, status="error", error_code="503")

            html_path = tracker.get_dashboard_path()
            js_path = tracker.js_data_file

            self.assertTrue(html_path.exists())
            self.assertTrue(js_path.exists())

            # Read js content
            js_text = js_path.read_text(encoding="utf-8")
            self.assertTrue(js_text.startswith("window.USAGE_DATA = {"))
            self.assertIn("gemini-2.5-flash", js_text)
            self.assertIn("503", js_text)

            # Read html template content
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("latencyTrendsChart", html_text)
            self.assertIn("latencyScatterChart", html_text)
            self.assertIn("reliabilityChart", html_text)
            self.assertIn("errorBreakdownChart", html_text)
            self.assertIn("avg-p50-latency", html_text)
            self.assertIn("overall-success-rate", html_text)

    @patch("agent.core.llm.get_genai_client")
    def test_llm_session_streaming_latency_and_error_recording(self, mock_get_client):
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_file = Path(tmp_dir) / "usage_history.json"
            custom_tracker = UsageTracker(persistence_file=persist_file)

            session = AgentChatSession("gpt-4o", session_id="test_session_latency")
            session.tracker = custom_tracker

            # 1. Test Mocked Streaming Success
            mock_client = MagicMock()
            mock_chunk1 = MagicMock()
            mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello", tool_calls=None))]
            mock_chunk2 = MagicMock()
            mock_chunk2.choices = [MagicMock(delta=MagicMock(content=" world!", tool_calls=None))]

            mock_client.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]
            mock_get_client.return_value = mock_client

            generator = session.send_message_stream("Hi")
            chunks = list(generator)
            self.assertEqual(len(chunks), 2)
            self.assertGreaterEqual(session._last_duration_ms, 0.0)
            self.assertIsNotNone(session._last_ttft_ms)

            # Record turn
            summary = session.record_turn_usage(assistant_response="Hello world!")
            self.assertEqual(summary["total_requests"], 1)

            # 2. Test Mocked API Error on create
            e_rate_limit = Exception("429 Too Many Requests")
            setattr(e_rate_limit, "status_code", 429)
            mock_client.chat.completions.create.side_effect = e_rate_limit

            with self.assertRaises(Exception):
                session.send_message_stream("Trigger rate limit")

            # Verify error recorded in custom_tracker
            today = list(custom_tracker.daily_usage.keys())[0]
            model_rec = custom_tracker.daily_usage[today]["gpt-4o"]
            self.assertEqual(model_rec["reliability"]["failure_count"], 1)
            self.assertEqual(model_rec["reliability"]["failure_reasons"]["429"], 1)


if __name__ == "__main__":
    unittest.main()
