"""Unit tests for cross-platform analytics scraper in scripts/analytics.py."""
import json
import unittest
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from scripts import analytics, ledger


class TestAnalyticsScraper(unittest.TestCase):
    """Test suite for metrics fetching, engagement scoring, and ledger integration."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("urllib.request.urlopen")
    def test_fetch_bluesky_metrics_success(self, mock_urlopen):
        mock_response_data = {
            "thread": {
                "post": {
                    "likeCount": 54,
                    "repostCount": 12,
                    "replyCount": 6,
                }
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        post_url = "https://bsky.app/profile/alice.bsky.social/post/3kxyz123"
        metrics = analytics.fetch_bluesky_metrics(post_url)

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["likes"], 54)
        self.assertEqual(metrics["reposts"], 12)
        self.assertEqual(metrics["replies"], 6)
        self.assertEqual(metrics["views"], 0)
        self.assertIn("updated_at", metrics)

    @patch("urllib.request.urlopen")
    def test_fetch_x_metrics_success(self, mock_urlopen):
        mock_response_data = {
            "favorite_count": 85,
            "retweet_count": 14,
            "conversation_count": 9,
            "views": {"count": "2400"},
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        post_url = "https://x.com/Lordporus/status/1234567890"
        metrics = analytics.fetch_x_metrics(post_url)

        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["likes"], 85)
        self.assertEqual(metrics["reposts"], 14)
        self.assertEqual(metrics["replies"], 9)
        self.assertEqual(metrics["views"], 2400)

    def test_calculate_engagement_score(self):
        metrics = {
            "likes": 50,
            "reposts": 10,  # 10 * 2 = 20
            "replies": 5,   # 5 * 3 = 15
            "views": 1000,  # 1000 / 100 = 10
        }
        # Expected: 50 + 20 + 15 + 10 = 95.0
        score = analytics.calculate_engagement_score(metrics)
        self.assertEqual(score, 95.0)

        # None / empty metrics
        self.assertEqual(analytics.calculate_engagement_score(None), 0.0)

    @patch.object(analytics, "fetch_bluesky_metrics")
    @patch.object(analytics, "fetch_x_metrics")
    def test_collect_metrics_updates_ledger(self, mock_x_fetch, mock_bsky_fetch):
        mock_bsky_fetch.return_value = {"likes": 30, "reposts": 5, "replies": 2, "views": 0}
        mock_x_fetch.return_value = {"likes": 100, "reposts": 20, "replies": 10, "views": 5000}

        # Setup state with 1 post
        now_iso = datetime.now(timezone.utc).isoformat()
        initial_state = {
            "version": "2.0",
            "posts": [
                {
                    "date": "2026-10-05",
                    "slot": "14:00",
                    "at": now_iso,
                    "text": "Cross-platform analytics test",
                    "platforms": {
                        "bluesky": {
                            "status": "published",
                            "url": "https://bsky.app/profile/user/post/1",
                            "verified": True,
                        },
                        "x": {
                            "status": "published",
                            "url": "https://x.com/user/status/2",
                            "verified": True,
                        },
                    },
                }
            ],
        }
        ledger.save_state(initial_state, self.state_file)

        res = analytics.collect_metrics(days=7, state_path=self.state_file)
        self.assertEqual(res["total_updated"], 2)
        self.assertEqual(res["platforms"]["bluesky"], 1)
        self.assertEqual(res["platforms"]["x"], 1)

        # Verify state updated on disk
        updated_state = ledger.load_state(self.state_file)
        b_metrics = updated_state["posts"][0]["platforms"]["bluesky"]["metrics"]
        self.assertEqual(b_metrics["likes"], 30)

    def test_generate_report_sorting(self):
        test_state = {
            "version": "2.0",
            "posts": [
                {
                    "date": "2026-10-05",
                    "slot": "13:00",
                    "text": "Low performer",
                    "platforms": {
                        "x": {
                            "status": "published",
                            "url": "https://x.com/1",
                            "metrics": {"likes": 5, "reposts": 1, "replies": 0, "views": 100},
                        }
                    },
                },
                {
                    "date": "2026-10-05",
                    "slot": "16:00",
                    "text": "High performer viral hit",
                    "platforms": {
                        "bluesky": {
                            "status": "published",
                            "url": "https://bsky.app/1",
                            "metrics": {"likes": 120, "reposts": 30, "replies": 15, "views": 0},
                        }
                    },
                },
            ],
        }
        ledger.save_state(test_state, self.state_file)

        report = analytics.generate_report(self.state_file)
        self.assertEqual(len(report), 2)
        # Higher score should be first
        self.assertEqual(report[0]["platform"], "bluesky")
        self.assertGreater(report[0]["score"], report[1]["score"])


if __name__ == "__main__":
    unittest.main()
