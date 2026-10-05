"""Unit tests for the LinkedInAdapter CDP text publishing driver."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.base import PlatformCapabilities, PublishPayload
from adapters.linkedin import LinkedInAdapter


class TestLinkedInAdapter(unittest.TestCase):
    """Test suite for LinkedInAdapter capabilities, rate-limiting, and actions."""

    def setUp(self):
        self.adapter = LinkedInAdapter(port=9444)

    def test_capabilities(self):
        caps = self.adapter.capabilities
        self.assertEqual(caps.max_characters, 3000)
        self.assertTrue(caps.supports_images)
        self.assertEqual(caps.max_images, 9)
        self.assertTrue(caps.supports_pdf_carousel)
        self.assertFalse(caps.requires_public_image_url)

    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_check_session_success(self, mock_ensure, mock_open):
        mock_page = AsyncMock()
        mock_page.eval.return_value = json.dumps({
            "logged_in": True,
            "handle": "lordporus-kumar",
        })
        mock_open.return_value = mock_page

        res = self.adapter.check_session()
        self.assertTrue(res["ok"])
        self.assertEqual(res["handle"], "lordporus-kumar")
        self.assertEqual(res["platform"], "linkedin")

    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
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

    @patch("adapters.linkedin.STATE_PATH")
    def test_rate_limit_blocks_when_less_than_min_gap(self, mock_state_path):
        mock_state_path.exists.return_value = True
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_state_path.read_text.return_value = json.dumps({
            "posts": [
                {
                    "at": recent_time,
                    "platform": "linkedin",
                    "verified": True,
                }
            ]
        })

        allowed, msg = self.adapter._check_rate_limit()
        self.assertFalse(allowed)
        self.assertIn("rate-limit guardrail", msg)

    @patch("adapters.linkedin.STATE_PATH")
    def test_rate_limit_allows_when_greater_than_min_gap(self, mock_state_path):
        mock_state_path.exists.return_value = True
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        mock_state_path.read_text.return_value = json.dumps({
            "posts": [
                {
                    "at": old_time,
                    "platform": "linkedin",
                    "verified": True,
                }
            ]
        })

        allowed, msg = self.adapter._check_rate_limit()
        self.assertTrue(allowed)
        self.assertIsNone(msg)

    @patch.object(LinkedInAdapter, "_check_rate_limit", return_value=(True, None))
    @patch.object(LinkedInAdapter, "_async_verify", return_value=True)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_text_success(self, mock_ensure, mock_open, mock_settle, mock_verify, mock_rate):
        mock_page = AsyncMock()
        # Mock eval responses for trigger, focus, submit
        mock_page.eval.side_effect = [
            "clicked",               # TRIGGER_COMPOSER_JS
            "focused",               # FOCUS_EDITOR_JS
            json.dumps({"clicked": True}),  # SUBMIT_POST_JS
        ]
        mock_open.return_value = mock_page

        payload = PublishPayload(text="Automated LinkedIn insight post.")
        res = self.adapter.publish(payload)

        self.assertEqual(res.platform, "linkedin")
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        mock_page.send.assert_any_call("Input.insertText", text="Automated LinkedIn insight post.")


if __name__ == "__main__":
    unittest.main()
