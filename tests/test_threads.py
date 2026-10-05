"""Unit tests for the Meta Threads CDP adapter."""
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.base import PlatformCapabilities, PublishPayload
from adapters.threads import ThreadsAdapter


class TestThreadsAdapter(unittest.TestCase):
    """Test suite for ThreadsAdapter capabilities, sessions, and publishing."""

    def setUp(self):
        self.adapter = ThreadsAdapter(port=9444, handle="lordporus_ai")

    def test_capabilities(self):
        caps = self.adapter.capabilities
        self.assertEqual(caps.max_characters, 500)
        self.assertTrue(caps.supports_images)
        self.assertEqual(caps.max_images, 10)
        self.assertFalse(caps.supports_pdf_carousel)
        self.assertFalse(caps.requires_public_image_url)

    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_check_session_logged_in(self, mock_ensure, mock_open):
        mock_page = AsyncMock()
        mock_page.eval.return_value = json.dumps({
            "logged_in": True,
            "handle": "lordporus_ai",
        })
        mock_open.return_value = mock_page

        res = self.adapter.check_session()
        self.assertTrue(res["ok"])
        self.assertEqual(res["handle"], "lordporus_ai")
        self.assertEqual(res["platform"], "threads")

    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_check_session_logged_out(self, mock_ensure, mock_open):
        mock_page = AsyncMock()
        mock_page.eval.return_value = json.dumps({
            "logged_in": False,
            "handle": None,
        })
        mock_open.return_value = mock_page

        res = self.adapter.check_session()
        self.assertFalse(res["ok"])
        self.assertIn("Not logged in", res["error"])

    @patch.object(ThreadsAdapter, "_async_verify", return_value=True)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_text_success(self, mock_ensure, mock_open, mock_settle, mock_verify):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            "clicked",                      # TRIGGER_COMPOSER_JS
            "focused",                      # FOCUS_EDITOR_JS
            json.dumps({"clicked": True}),  # SUBMIT_POST_JS
        ]
        mock_open.return_value = mock_page

        payload = PublishPayload(text="Hello Threads world from OmniPost V2!")
        res = self.adapter.publish(payload)

        self.assertEqual(res.platform, "threads")
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertIn("lordporus_ai", res.url)
        mock_page.send.assert_any_call("Input.insertText", text="Hello Threads world from OmniPost V2!")

    @patch.object(ThreadsAdapter, "_attach_media", new_callable=AsyncMock)
    @patch.object(ThreadsAdapter, "_async_verify", return_value=True)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_with_image_attachment(
        self, mock_ensure, mock_open, mock_settle, mock_verify, mock_attach
    ):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            "clicked",
            "focused",
            json.dumps({"clicked": True}),
        ]
        mock_open.return_value = mock_page
        mock_attach.return_value = True

        dummy_img = Path("scratch/test_thread.png")
        dummy_img.parent.mkdir(parents=True, exist_ok=True)
        dummy_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimage")

        try:
            payload = PublishPayload(
                text="Post with attached image",
                media_paths=[dummy_img],
            )
            res = self.adapter.publish(payload)
            self.assertTrue(res.success)
            mock_attach.assert_called_once_with(mock_page, dummy_img)
        finally:
            if dummy_img.exists():
                dummy_img.unlink()

    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    def test_verify_activity_matches(self, mock_open, mock_settle):
        mock_page = AsyncMock()
        mock_page.eval.return_value = json.dumps([
            "Hello Threads world from OmniPost V2! This is live.",
            "Older thread from yesterday",
        ])
        mock_open.return_value = mock_page

        matched = self.adapter.verify(None, "Hello Threads world from OmniPost V2!")
        self.assertTrue(matched)


if __name__ == "__main__":
    unittest.main()
