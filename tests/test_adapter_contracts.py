"""Phase 13 adapter contract tests.

These tests deliberately mock CDP/page objects: no browser or network access is
required. They pin the recovery behaviour that failed in the live run.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from adapters.linkedin import LinkedInAdapter
from adapters.threads import ThreadsAdapter
from adapters.x import XAdapter
from adapters.base import PublishPayload
from scripts.errors import RateLimitError, SelectorError


class TestLinkedInComposerContracts(unittest.TestCase):
    def setUp(self):
        self.adapter = LinkedInAdapter(port=9444)

    def test_linkedin_composer_prefers_scoped_selector(self):
        source = Path("adapters/linkedin.py").read_text(encoding="utf-8")
        self.assertNotIn("artdeco-button--tertiary", source)

        from adapters.linkedin import TRIGGER_COMPOSER_JS

        share_box = TRIGGER_COMPOSER_JS.index('button[id*="share-box"]')
        text_fallback = TRIGGER_COMPOSER_JS.index("text:start-a-post")
        self.assertLess(share_box, text_fallback)
        self.assertIn("candidates", TRIGGER_COMPOSER_JS)

    @patch("adapters.linkedin.asyncio.sleep", new_callable=AsyncMock)
    @patch.object(LinkedInAdapter, "_check_rate_limit", return_value=(True, None))
    @patch.object(LinkedInAdapter, "_async_verify", return_value=True)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_linkedin_composer_waits_for_dialog(
        self, mock_ensure, mock_open, mock_settle, mock_verify, mock_rate, mock_sleep
    ):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            {"result": "clicked", "selector": 'button[id*="share-box"]', "candidates": 1},
            "no_dialog",
            "focused",
            None,  # input/change dispatch
            json.dumps({"clicked": True}),
            "success_toast_detected",
        ]
        mock_open.return_value = mock_page

        result = self.adapter.publish(PublishPayload(text="Delayed dialog test"))

        self.assertTrue(result.success)
        from adapters.linkedin import FOCUS_EDITOR_JS

        focus_calls = [
            call for call in mock_page.eval.call_args_list
            if call.args and call.args[0] == FOCUS_EDITOR_JS
        ]
        self.assertGreaterEqual(len(focus_calls), 2, "the dialog/editor should be polled")


class TestLinkedInRateLimitContracts(unittest.TestCase):
    def setUp(self):
        self.adapter = LinkedInAdapter(port=9444)

    def test_linkedin_rate_limit_uses_platform_at(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps({
                    "posts": [{
                        "at": "2020-01-01T00:00:00+00:00",
                        "platform": "linkedin",
                        "platforms": {
                            "linkedin": {
                                "at": recent,
                                "status": "published_verified",
                                "verified": True,
                            }
                        },
                    }]
                }),
                encoding="utf-8",
            )
            with patch("adapters.linkedin.STATE_PATH", state_path):
                allowed, message = self.adapter._check_rate_limit()

        self.assertFalse(allowed)
        self.assertIn("rate-limit guardrail", message)

    def test_linkedin_rate_limit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps({
                    "posts": [{
                        "platforms": {"linkedin": {"at": "not-a-timestamp"}}
                    }]
                }),
                encoding="utf-8",
            )
            with patch("adapters.linkedin.STATE_PATH", state_path):
                with self.assertRaises(RateLimitError) as raised:
                    self.adapter._check_rate_limit()

        self.assertEqual(raised.exception.platform, "linkedin")
        self.assertEqual(raised.exception.stage, "rate_limit")
        self.assertIn("at", raised.exception.context)


class TestThreadsPermalinkContracts(unittest.TestCase):
    def setUp(self):
        self.adapter = ThreadsAdapter(port=9444, handle="lordporus_ai")

    @patch.object(ThreadsAdapter, "get_base_url", return_value="https://www.threads.net/")
    @patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock)
    @patch.object(ThreadsAdapter, "_async_verify", return_value=True)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_threads_returns_toast_permalink(
        self, mock_ensure, mock_open, mock_settle, mock_verify, mock_sleep, mock_base
    ):
        mock_page = AsyncMock()
        permalink = "https://www.threads.net/@lordporus_ai/post/ABC123"
        mock_page.eval.side_effect = [
            "clicked",
            "focused",
            json.dumps({"clicked": True}),
            permalink,
        ]
        mock_open.return_value = mock_page

        result = self.adapter.publish(PublishPayload(text="Permalink test"))

        self.assertTrue(result.success)
        self.assertTrue(result.verified)
        self.assertEqual(result.url, permalink)
        self.assertEqual(result.post_id, "ABC123")
        mock_verify.assert_not_called()

    @patch.object(ThreadsAdapter, "get_base_url", return_value="https://www.threads.net/")
    @patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock)
    @patch.object(ThreadsAdapter, "_async_verify", return_value=False)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.threads.ThreadsAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_threads_missing_permalink_is_unverified(
        self, mock_ensure, mock_open, mock_settle, mock_verify, mock_sleep, mock_base
    ):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            "clicked",
            "focused",
            json.dumps({"clicked": True}),
            None,
            None,
            None,
            None,
            None,
        ]
        mock_open.return_value = mock_page

        result = self.adapter.publish(PublishPayload(text="Missing permalink test"))

        self.assertTrue(result.success)
        self.assertFalse(result.verified)
        self.assertIsNone(result.url)
        self.assertEqual(
            result.raw_response["profile_url"],
            "https://www.threads.net/@lordporus_ai",
        )
        self.assertNotEqual(result.url, result.raw_response["profile_url"])


class TestXMediaContracts(unittest.TestCase):
    def setUp(self):
        self.adapter = XAdapter(port=9444)

    @patch("scripts.browser.ensure_chrome", return_value=True)
    @patch("scripts.post.do_post")
    def test_x_attaches_all_cards(self, mock_do_post, mock_ensure):
        async def fake_do_post(text, image=None, images=None, **kwargs):
            return {
                "posted": True,
                "tweet_url": "https://x.com/OmniPostHQ/status/123",
                "verified": True,
                "error": None,
            }

        mock_do_post.side_effect = fake_do_post
        paths = [Path("card1.png"), Path("card2.png"), Path("card3.png")]

        result = self.adapter.publish(PublishPayload(text="Storybook", media_paths=paths))

        self.assertTrue(result.success)
        mock_do_post.assert_called_once_with(text="Storybook", images=paths)


class TestTypedAdapterErrors(unittest.TestCase):
    def test_typed_error_context(self):
        error = SelectorError(
            "composer control missing",
            platform="linkedin",
            stage="composer_open",
            selector='button[id*="share-box"]',
            candidates=2,
            context={"extra": True},
        )

        self.assertEqual(error.platform, "linkedin")
        self.assertEqual(error.stage, "composer_open")
        self.assertEqual(error.context["selector"], 'button[id*="share-box"]')
        self.assertEqual(error.context["candidates"], 2)
        self.assertEqual(error.context["extra"], True)
        self.assertEqual(error.selector, 'button[id*="share-box"]')


if __name__ == "__main__":
    unittest.main()
