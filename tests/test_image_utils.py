"""
Unit tests for image ingestion and encoding utilities (US-IMAGE-001).
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import io
from PIL import Image

from agent.utils import (
    encode_image_file,
    grab_clipboard_image,
    create_multimodal_content,
    SUPPORTED_IMAGE_EXTENSIONS,
)


class TestImageUtils(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Create a small valid test PNG
        self.test_png = self.dir_path / "test.png"
        img = Image.new("RGB", (30, 30), color="blue")
        img.save(self.test_png, format="PNG")

        # Create a small valid test JPEG
        self.test_jpg = self.dir_path / "test.jpg"
        img.save(self.test_jpg, format="JPEG")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_encode_valid_png(self):
        res = encode_image_file(str(self.test_png))
        self.assertTrue(res["success"])
        self.assertEqual(res["mime_type"], "image/png")
        self.assertEqual(res["file_name"], "test.png")
        self.assertTrue(res["data_uri"].startswith("data:image/png;base64,"))
        self.assertGreater(res["size_bytes"], 0)

    def test_encode_valid_jpeg(self):
        res = encode_image_file(str(self.test_jpg))
        self.assertTrue(res["success"])
        self.assertEqual(res["mime_type"], "image/jpeg")
        self.assertTrue(res["data_uri"].startswith("data:image/jpeg;base64,"))

    def test_encode_quoted_path(self):
        quoted = f'"{self.test_png}"'
        res = encode_image_file(quoted)
        self.assertTrue(res["success"])
        self.assertEqual(res["file_name"], "test.png")

    def test_encode_nonexistent_file(self):
        res = encode_image_file(str(self.dir_path / "missing.png"))
        self.assertFalse(res["success"])
        self.assertIn("does not exist", res["error"])

    def test_encode_unsupported_extension(self):
        txt_file = self.dir_path / "test.txt"
        txt_file.write_text("hello", encoding="utf-8")
        res = encode_image_file(str(txt_file))
        self.assertFalse(res["success"])
        self.assertIn("Unsupported image format", res["error"])

    @patch("agent.utils.MAX_IMAGE_SIZE_BYTES", 100)
    def test_encode_oversized_file(self):
        res = encode_image_file(str(self.test_png))
        self.assertFalse(res["success"])
        self.assertIn("too large", res["error"])

    @patch("PIL.ImageGrab.grabclipboard")
    def test_grab_clipboard_empty(self, mock_grab):
        mock_grab.return_value = None
        res = grab_clipboard_image()
        self.assertFalse(res["success"])
        self.assertIn("No image found in clipboard", res["error"])

    @patch("PIL.ImageGrab.grabclipboard")
    def test_grab_clipboard_bitmap(self, mock_grab):
        fake_img = Image.new("RGB", (20, 20), color="red")
        mock_grab.return_value = fake_img

        res = grab_clipboard_image()
        self.assertTrue(res["success"])
        self.assertEqual(res["mime_type"], "image/png")
        self.assertEqual(res["file_name"], "clipboard_screenshot.png")
        self.assertTrue(res["data_uri"].startswith("data:image/png;base64,"))
        self.assertEqual(res["width"], 20)
        self.assertEqual(res["height"], 20)

    @patch("PIL.ImageGrab.grabclipboard")
    def test_grab_clipboard_file_list(self, mock_grab):
        mock_grab.return_value = [str(self.test_png)]

        res = grab_clipboard_image()
        self.assertTrue(res["success"])
        self.assertEqual(res["file_name"], "test.png")

    def test_create_multimodal_content_structure(self):
        uri = "data:image/png;base64,dGVzdA=="
        content = create_multimodal_content("Explain this diagram", uri)

        self.assertIsInstance(content, list)
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0], {"type": "text", "text": "Explain this diagram"})
        self.assertEqual(content[1], {"type": "image_url", "image_url": {"url": uri}})


if __name__ == "__main__":
    unittest.main()
