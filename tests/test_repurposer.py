"""Unit tests for the scripts.repurpose engine and polymorphic autoposter dispatch."""
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from adapters.base import PlatformCapabilities, PublishPayload, PublishResult
from scripts import autoposter
from scripts.repurpose import (
    format_bluesky,
    format_linkedin,
    format_threads,
    format_x,
    repurpose_topic,
)


class TestContentRepurposer(unittest.TestCase):
    """Test suite for individual platform copy formatters and schema emission."""

    def test_format_x_length_and_structure(self):
        headline = "Breaking: Local AI models just beat cloud inference in latency benchmarks"
        points = [
            "Quantized kernels run 4x faster on Apple Silicon and RTX cards",
            "Zero privacy leaks and zero per-token API bills",
            "Open source ecosystem leads in edge efficiency",
        ]
        formatted = format_x(headline, points)
        self.assertLessEqual(len(formatted), 280)
        self.assertIn("Breaking:", formatted)
        self.assertIn("• Quantized kernels", formatted)

    def test_format_bluesky_length_and_structure(self):
        headline = "New paper proves deterministic state machines reduce agent hallucinations by 80%."
        points = [
            "Strict Pydantic schemas prevent malformed tool inputs.",
            "Atomic ledgers isolate network failures.",
        ]
        formatted = format_bluesky(headline, points)
        self.assertLessEqual(len(formatted), 300)
        self.assertIn("(1)", formatted)
        self.assertIn("(2)", formatted)

    def test_format_linkedin_storytelling_and_cta(self):
        headline = "Why your engineering team should rethink its AI stack."
        body = "We spent 3 months deploying autonomous agents across multiple social channels. Here is what broke:"
        points = [
            "Relying on paid APIs gets expensive quickly ($200+/mo).",
            "Single-network copy fails to resonate on multi-platform feeds.",
        ]
        takeaway = "Build on local tools and open protocols."
        formatted = format_linkedin(headline, body, points, takeaway)

        self.assertIn("Key Engineering Takeaways:", formatted)
        self.assertIn("▸ Relying on paid APIs", formatted)
        self.assertIn("architecture carousel below", formatted)
        self.assertGreater(len(formatted), 250)

    def test_format_threads_conversational(self):
        headline = "Local AI models are now faster than cloud APIs on modern hardware."
        takeaway = "Are you still paying OpenAI per token, or running local models?"
        formatted = format_threads(headline, takeaway)
        self.assertLessEqual(len(formatted), 500)
        self.assertIn("paying OpenAI", formatted)

    @patch("scripts.repurpose.create_carousel_pdf")
    @patch("scripts.repurpose.create_infocard")
    def test_repurpose_topic_structure(self, mock_card, mock_carousel):
        topic_data = {
            "headline": "Autonomous Agents Architecture",
            "body": "Detailed case study on deterministic pipelines.",
            "points": ["Rule 1", "Rule 2", "Rule 3"],
            "takeaway": "Reliability requires code-level constraints.",
            "category": "ENGINEERING",
        }
        res = repurpose_topic(topic_data, generate_media=False)

        self.assertIn("x", res)
        self.assertIn("bluesky", res)
        self.assertIn("linkedin", res)
        self.assertIn("threads", res)

        self.assertTrue(res["x"]["enabled"])
        self.assertEqual(res["linkedin"]["media_type"], "carousel")
        self.assertIn("document_title", res["linkedin"])


class TestPolymorphicAutoposter(unittest.TestCase):
    """Test suite ensuring autoposter routes platform-specific text from polymorphic draft."""

    @patch("scripts.autoposter.ensure_daily_plan")
    @patch("scripts.autoposter.run_cmd")
    @patch("scripts.settings.get_active_adapters")
    def test_autoposter_dispatches_tailored_copy(
        self, mock_get_adapters, mock_run_cmd, mock_plan
    ):
        poly_due_item = {
            "slot": "16:00",
            "kind": "ai_update",
            "text": "Default generic text",
            "platforms": {
                "x": {"enabled": True, "text": "Tailored X Copy", "media": []},
                "bluesky": {"enabled": True, "text": "Tailored Bluesky Copy", "media": []},
                "linkedin": {"enabled": True, "text": "Tailored LinkedIn Longform", "media": []},
                "threads": {"enabled": False, "text": "Disabled Threads Copy"},
            },
        }

        mock_run_cmd.side_effect = [
            (0, json.dumps(poly_due_item)),
            (0, "marked"),
        ]

        mock_x = MagicMock()
        mock_x.platform_name = "x"
        mock_x.capabilities = PlatformCapabilities(max_characters=280)
        mock_x.publish.return_value = PublishResult(platform="x", success=True, url="https://x.com/1")

        mock_bsky = MagicMock()
        mock_bsky.platform_name = "bluesky"
        mock_bsky.capabilities = PlatformCapabilities(max_characters=300)
        mock_bsky.publish.return_value = PublishResult(platform="bluesky", success=True, url="https://bsky.app/1")

        mock_link = MagicMock()
        mock_link.platform_name = "linkedin"
        mock_link.capabilities = PlatformCapabilities(max_characters=3000)
        mock_link.publish.return_value = PublishResult(platform="linkedin", success=True, url="https://linkedin.com/1")

        mock_thrd = MagicMock()
        mock_thrd.platform_name = "threads"
        mock_thrd.capabilities = PlatformCapabilities(max_characters=500)

        mock_get_adapters.return_value = [mock_x, mock_bsky, mock_link, mock_thrd]

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            dummy_state = Path(td) / "state.json"
            with patch("scripts.ledger.STATE_PATH", dummy_state), \
                 patch("scripts.autoposter.ledger.STATE_PATH", dummy_state), \
                 patch("sys.argv", ["autoposter.py"]):
                code = autoposter.main()

        self.assertEqual(code, 0)
        # Check that X received Tailored X Copy
        x_call = mock_x.publish.call_args[0][0]
        self.assertEqual(x_call.text, "Tailored X Copy")

        # Check that Bluesky received Tailored Bluesky Copy
        bsky_call = mock_bsky.publish.call_args[0][0]
        self.assertEqual(bsky_call.text, "Tailored Bluesky Copy")

        # Check that LinkedIn received Longform Copy
        link_call = mock_link.publish.call_args[0][0]
        self.assertEqual(link_call.text, "Tailored LinkedIn Longform")

        # Check that Threads was skipped because enabled=False in slot
        mock_thrd.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
