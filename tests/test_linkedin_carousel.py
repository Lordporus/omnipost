"""Unit tests for LinkedInAdapter document carousel uploading and activity read-back verification."""
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.base import PublishPayload
from adapters.linkedin import LinkedInAdapter


class TestLinkedInCarouselAndVerification(unittest.TestCase):
    """Test suite for PDF document carousel integration and activity verification."""

    def setUp(self):
        self.adapter = LinkedInAdapter(port=9444)

    @patch("adapters.linkedin.LinkedInAdapter._attach_document", new_callable=AsyncMock)
    @patch.object(LinkedInAdapter, "_check_rate_limit", return_value=(True, None))
    @patch.object(LinkedInAdapter, "_async_verify", return_value=True)
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_carousel_delegates_to_attach_document(
        self, mock_ensure, mock_open, mock_settle, mock_verify, mock_rate, mock_attach
    ):
        mock_page = AsyncMock()
        mock_page.eval.side_effect = [
            "clicked",                      # TRIGGER_COMPOSER_JS
            "focused",                      # FOCUS_EDITOR_JS
            json.dumps({"clicked": True}),  # SUBMIT_POST_JS
        ]
        mock_open.return_value = mock_page
        mock_attach.return_value = True

        dummy_pdf = Path("scratch/test_deck.pdf")
        dummy_pdf.parent.mkdir(parents=True, exist_ok=True)
        dummy_pdf.write_bytes(b"%PDF-1.4 mock pdf data")

        try:
            payload = PublishPayload(
                text="5 Lessons on Autonomous AI Architectures\nSwipe to read ➔",
                media_paths=[dummy_pdf],
                media_type="carousel",
                extra_metadata={"document_title": "AI Architecture Deck"},
            )

            res = self.adapter.publish(payload)
            self.assertTrue(res.success)
            self.assertEqual(res.platform, "linkedin")
            self.assertTrue(res.verified)
            mock_attach.assert_called_once_with(mock_page, dummy_pdf, "AI Architecture Deck")
        finally:
            if dummy_pdf.exists():
                dummy_pdf.unlink()

    @patch("adapters.linkedin.LinkedInAdapter._attach_document", new_callable=AsyncMock)
    @patch.object(LinkedInAdapter, "_check_rate_limit", return_value=(True, None))
    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    @patch("scripts.browser.ensure_chrome")
    def test_publish_carousel_fails_if_document_attachment_fails(
        self, mock_ensure, mock_open, mock_settle, mock_rate, mock_attach
    ):
        mock_page = AsyncMock()
        mock_page.eval.return_value = "clicked"
        mock_open.return_value = mock_page
        mock_attach.return_value = False

        dummy_pdf = Path("scratch/failing_deck.pdf")
        dummy_pdf.parent.mkdir(parents=True, exist_ok=True)
        dummy_pdf.write_bytes(b"%PDF-1.4 mock pdf data")

        try:
            payload = PublishPayload(
                text="Failing document attachment test",
                media_paths=[dummy_pdf],
                media_type="carousel",
            )
            res = self.adapter.publish(payload)
            self.assertFalse(res.success)
            self.assertIn("Failed to attach PDF carousel document", res.error)
        finally:
            if dummy_pdf.exists():
                dummy_pdf.unlink()

    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    def test_verify_activity_matches_text_success(self, mock_open, mock_settle):
        mock_page = AsyncMock()
        mock_page.eval.return_value = json.dumps([
            {"text": "5 Lessons on Autonomous AI Architectures - Detailed overview below", "urn": "urn:li:activity:1001"},
            {"text": "Older post from last week", "urn": "urn:li:activity:999"},
        ])
        mock_open.return_value = mock_page

        matched = self.adapter.verify(None, "5 Lessons on Autonomous AI Architectures")
        self.assertTrue(matched)

    @patch("scripts.browser.settle_page", new_callable=AsyncMock)
    @patch("adapters.linkedin.LinkedInAdapter._open_stealth")
    def test_verify_activity_fails_when_unmatched(self, mock_open, mock_settle):
        mock_page = AsyncMock()
        mock_page.eval.return_value = json.dumps([
            {"text": "Unrelated topic post", "urn": "urn:li:activity:555"},
        ])
        mock_open.return_value = mock_page

        # Force short timeout in test by mocking time
        with patch("time.time", side_effect=[100.0, 150.0]):
            matched = self.adapter.verify(None, "Specific missing headline")
            self.assertFalse(matched)


if __name__ == "__main__":
    unittest.main()
