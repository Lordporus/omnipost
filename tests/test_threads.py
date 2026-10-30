"""Unit tests for the Meta Threads CDP adapter."""
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from adapters import threads as threads_mod
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

    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_check_session_logged_in(self, mock_ensure, mock_open, mock_settle):
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

    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_check_session_logged_out(self, mock_ensure, mock_open, mock_settle):
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
    @patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_text_success(self, mock_ensure, mock_open, mock_settle, mock_sleep, mock_verify):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            json.dumps({"loading": False, "button": True}),  # HYDRATED_JS
            "clicked",                      # TRIGGER_COMPOSER_JS
            "focused",                      # FOCUS_EDITOR_JS
            json.dumps({"clicked": True}),  # SUBMIT_POST_JS
            json.dumps({"editor_open": False, "posted": True}),  # SUBMIT_CONFIRMED_JS
            "https://www.threads.net/@lordporus_ai/post/ABC123",  # THREADS_PERMALINK_JS
        ]
        mock_open.return_value = mock_page

        payload = PublishPayload(text="Hello Threads world from OmniPost V2!")
        res = self.adapter.publish(payload)

        self.assertEqual(res.platform, "threads")
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertEqual(res.url, "https://www.threads.net/@lordporus_ai/post/ABC123")
        self.assertEqual(res.post_id, "ABC123")
        mock_verify.assert_not_called()
        mock_page.send.assert_any_call("Input.insertText", text="Hello Threads world from OmniPost V2!")

    def test_own_permalink_requires_configured_handle(self):
        self.assertTrue(self.adapter._is_own_permalink(
            "https://www.threads.com/@lordporus_ai/post/ABC123"
        ))
        self.assertFalse(self.adapter._is_own_permalink(
            "https://www.threads.com/@gabbzkieeee/post/De6nyCpGKgI"
        ))
        self.assertFalse(self.adapter._is_own_permalink(
            "https://www.threads.com/@lordporus_ai"
        ))

    @patch.object(ThreadsAdapter, "_async_verify", return_value=True)
    @patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_rejects_foreign_permalink_and_reads_back(
        self, mock_ensure, mock_open, mock_settle, mock_sleep, mock_verify
    ):
        foreign = "https://www.threads.com/@gabbzkieeee/post/De6nyCpGKgI"
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            json.dumps({"loading": False, "button": True}),  # HYDRATED_JS
            "clicked",
            "focused",
            json.dumps({"clicked": True}),
            json.dumps({"editor_open": False, "posted": True}),
            *([foreign] * 5),
        ]
        mock_open.return_value = mock_page

        payload = PublishPayload(text="Phronix test post")
        res = self.adapter.publish(payload)

        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertIsNone(res.url)
        self.assertIsNone(res.post_id)
        self.assertEqual(res.raw_response["verification_source"], "readback")
        mock_verify.assert_called_once_with(None, "Phronix test post")

    def test_threads_base_url(self):
        from adapters.threads import THREADS_BASE_URL
        self.assertEqual(THREADS_BASE_URL, "https://www.threads.net/")

    @patch("scripts.settings.load", return_value={})
    @patch("scripts.browser.alive", return_value=True)
    @patch("scripts.browser.list_tabs", return_value=[{"url": "https://www.threads.com/@lordporus"}])
    def test_get_base_url_detects_com(self, mock_tabs, mock_alive, mock_load):
        url = self.adapter.get_base_url()
        self.assertEqual(url, "https://www.threads.com/")

    @patch("scripts.settings.load", return_value={})
    @patch("scripts.browser.alive", return_value=True)
    @patch("scripts.browser.list_tabs", return_value=[{"url": "https://www.threads.net/@lordporus"}])
    def test_get_base_url_detects_net(self, mock_tabs, mock_alive, mock_load):
        url = self.adapter.get_base_url()
        self.assertEqual(url, "https://www.threads.net/")

    @patch.object(ThreadsAdapter, "_attach_media", new_callable=AsyncMock)
    @patch.object(ThreadsAdapter, "_async_verify", return_value=True)
    @patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_with_image_attachment(
        self, mock_ensure, mock_open, mock_settle, mock_sleep, mock_verify, mock_attach
    ):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            json.dumps({"loading": False, "button": True}),  # HYDRATED_JS
            "clicked",
            "focused",
            json.dumps({"clicked": True}),
            json.dumps({"editor_open": False, "posted": True}),
            "https://www.threads.net/@lordporus_ai/post/IMG123",
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
            mock_attach.assert_called_once_with(mock_page, [dummy_img])
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

    def test_submit_targets_composer_not_feed(self):
        """The Post button must be resolved from the composer that owns the editor.

        The feed renders its own inline "What's new?" composer with a Post
        button that comes first in DOM order; a document-wide search clicks it
        and silently submits nothing.
        """
        js = threads_mod.SUBMIT_POST_JS
        self.assertIn("composer_not_laid_out", js)
        self.assertIn("getBoundingClientRect", js)
        self.assertIn("parentElement", js)  # walks up from the editor
        self.assertNotIn("document.querySelectorAll('div[role=\"button\"]", js)
        self.assertNotIn("aria-disabled", js)  # Threads never sets it

    def test_submit_fails_closed_when_composer_zero_sized(self):
        """A 0x0 composer is a broken layout, not a submit."""
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            json.dumps({"loading": False, "button": True}),
            "clicked",
            "focused",
            json.dumps({"error": "composer_not_laid_out"}),
        ]

        with patch("adapters.threads.ThreadsAdapter._open_stealth", new=AsyncMock(return_value=mock_page)), \
             patch("scripts.browser.ensure_chrome"), \
             patch("scripts.browser.settle_page", new_callable=AsyncMock), \
             patch("adapters.threads.capture_failure_artifacts", new_callable=AsyncMock,
                   return_value={"summary": "x"}):
            res = self.adapter.publish(PublishPayload(text="Phronix test post"))

        self.assertFalse(res.success)
        self.assertIn("composer_not_laid_out", res.error)

    @patch.object(ThreadsAdapter, "_async_verify", return_value=False)
    @patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_unconfirmed_submit_is_failure(
        self, mock_ensure, mock_open, mock_settle, mock_sleep, mock_verify
    ):
        """A click that leaves the composer open must fail, not report unverified."""
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            json.dumps({"loading": False, "button": True}),
            "clicked",
            "focused",
            json.dumps({"clicked": True}),
            *([json.dumps({"editor_open": True, "posted": False})] * 20),
        ]
        mock_open.return_value = mock_page

        with patch("adapters.threads.capture_failure_artifacts", new_callable=AsyncMock,
                   return_value={"summary": "x"}):
            res = self.adapter.publish(PublishPayload(text="Phronix test post"))

        self.assertFalse(res.success)
        self.assertIn("not confirmed", res.error)
        mock_verify.assert_not_called()

    def test_permalink_ignores_feed_links(self):
        """A /post/ link anywhere in the main feed is not proof of this post."""
        js = threads_mod.THREADS_PERMALINK_JS
        self.assertNotIn('div[role="main"]', js)
        self.assertIn('div[data-pressable-container="true"]', js)

    def test_verify_scans_post_containers_not_page_chrome(self):
        """The profile has 40+ pressable divs; the live post sits at index 19.

        Selecting the first six of the union with div.x1i10hfl returned only
        nav chrome ('' / 'Edit' / 'Show more' / 'New thread'), so a published
        post could never be verified.
        """
        js = threads_mod.THREADS_VERIFY_JS
        self.assertIn('div[data-pressable-container="true"]', js)
        self.assertNotIn("x1i10hfl", js)
        self.assertNotIn("slice(0, 6)", js)


if __name__ == "__main__":
    unittest.main()
