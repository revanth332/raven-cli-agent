"""
Unit tests for model vision capability detection and Vision Bridge (US-IMAGE-002).
"""

import unittest
from unittest.mock import patch, MagicMock

from agent.core.vision import (
    is_model_vision_capable,
    transcribe_image_with_vision_model,
)


class TestVisionCapability(unittest.TestCase):

    def test_vision_capable_models(self):
        models = [
            "google/gemini-2.5-flash",
            "google/gemini-1.5-pro",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-3-5-sonnet",
            "anthropic/claude-3-opus",
            "mistralai/pixtral-12b",
            "qwen/qwen-2-vl-72b-instruct",
            "meta-llama/llama-3.2-11b-vision-instruct",
        ]
        for m in models:
            self.assertTrue(is_model_vision_capable(m), f"Expected {m} to be vision-capable")

    def test_text_only_models(self):
        models = [
            "cohere/north-mini-code:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "deepseek/deepseek-coder",
            "openrouter/free",
            "meta-llama/llama-3.1-8b-instruct",
            "",
            None,
        ]
        for m in models:
            self.assertFalse(is_model_vision_capable(m), f"Expected {m} to be text-only")

    @patch("agent.core.llm.get_genai_client")
    def test_transcribe_image_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Error: Null pointer at line 42."
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        res = transcribe_image_with_vision_model("data:image/png;base64,abc", query="What is the error?")
        self.assertTrue(res["success"])
        self.assertEqual(res["transcription"], "Error: Null pointer at line 42.")
        self.assertIn("gemini", res["model_used"].lower())

    @patch("agent.core.llm.get_genai_client")
    def test_transcribe_image_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API key invalid")
        mock_get_client.return_value = mock_client

        res = transcribe_image_with_vision_model("data:image/png;base64,abc")
        self.assertFalse(res["success"])
        self.assertIn("Vision Bridge transcription failed", res["error"])


if __name__ == "__main__":
    unittest.main()
