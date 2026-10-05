"""Unit tests for Unified State Ledger (Schema v2.0) in scripts/ledger.py."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adapters.base import PublishResult
from scripts import ledger


class TestStateLedger(unittest.TestCase):
    """Test suite for state ledger migration, atomic writes, and per-platform status."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.test_state_file = Path(self.temp_dir.name) / "state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migrate_legacy_v1_state(self):
        """Verify legacy v1 state with single tweet_url is migrated to v2 with platforms dict."""
        legacy_data = {
            "handle": "testuser",
            "ai_update_day": 2,
            "posts": [
                {
                    "at": "2026-10-04T12:00:00.000Z",
                    "slot": "13:00",
                    "kind": "value",
                    "text": "A great insight about AI agents",
                    "tweet_url": "https://x.com/testuser/status/1001",
                    "verified": True,
                },
                {
                    "at": "2026-10-04T16:00:00.000Z",
                    "slot": "16:00",
                    "kind": "ai_update",
                    "text": "AI Update Day 2",
                    "tweet_url": None,
                    "verified": False,
                },
            ],
        }

        migrated = ledger.migrate_state(legacy_data)
        self.assertEqual(migrated["version"], "2.0")
        self.assertEqual(len(migrated["posts"]), 2)

        p1 = migrated["posts"][0]
        self.assertIn("platforms", p1)
        self.assertIn("x", p1["platforms"])
        self.assertEqual(p1["platforms"]["x"]["status"], "published")
        self.assertEqual(p1["platforms"]["x"]["url"], "https://x.com/testuser/status/1001")
        self.assertTrue(p1["platforms"]["x"]["verified"])
        self.assertEqual(p1["date"], "2026-10-04")

        p2 = migrated["posts"][1]
        self.assertIn("x", p2["platforms"])
        self.assertEqual(p2["platforms"]["x"]["status"], "failed")
        self.assertFalse(p2["platforms"]["x"]["verified"])

    def test_atomic_save_and_load(self):
        """Verify atomic save creates valid file that can be loaded cleanly."""
        data = {
            "version": "2.0",
            "handle": "alice",
            "posts": [],
        }
        ledger.save_state(data, self.test_state_file)
        self.assertTrue(self.test_state_file.exists())

        loaded = ledger.load_state(self.test_state_file)
        self.assertEqual(loaded["handle"], "alice")
        self.assertEqual(loaded["version"], "2.0")

    def test_record_platform_status_with_publish_result(self):
        """Verify recording PublishResult creates/updates post entry properly."""
        state = ledger.load_state(self.test_state_file)

        res = PublishResult(
            platform="bluesky",
            success=True,
            url="https://bsky.app/profile/alice.bsky.social/post/123",
            verified=True,
        )

        ledger.record_platform_status(
            state,
            date="2026-10-05",
            slot="14:00",
            platform="bluesky",
            result=res,
            text="Cross-platform test",
            path=self.test_state_file,
        )

        self.assertTrue(ledger.is_platform_done(state, "2026-10-05", "14:00", "bluesky"))
        self.assertFalse(ledger.is_platform_done(state, "2026-10-05", "14:00", "x"))

        # Verify persisted state on disk
        disk_state = ledger.load_state(self.test_state_file)
        entry = ledger.get_slot_entry(disk_state, "2026-10-05", "14:00")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["platforms"]["bluesky"]["url"], "https://bsky.app/profile/alice.bsky.social/post/123")
        self.assertTrue(entry["platforms"]["bluesky"]["verified"])

    def test_pending_and_fully_published_queries(self):
        """Verify get_pending_platforms and is_slot_fully_published logic."""
        state = ledger.load_state(self.test_state_file)
        targets = ["x", "bluesky", "linkedin", "threads"]

        # Initially, all are pending
        pending = ledger.get_pending_platforms(state, "2026-10-05", "16:00", targets)
        self.assertEqual(pending, targets)
        self.assertFalse(ledger.is_slot_fully_published(state, "2026-10-05", "16:00", targets))

        # Record success for x and bluesky
        ledger.record_platform_status(
            state, "2026-10-05", "16:00", "x",
            PublishResult(platform="x", success=True, url="https://x.com/1", verified=True),
            path=self.test_state_file,
        )
        ledger.record_platform_status(
            state, "2026-10-05", "16:00", "bluesky",
            PublishResult(platform="bluesky", success=True, url="https://bsky.app/1", verified=True),
            path=self.test_state_file,
        )

        pending = ledger.get_pending_platforms(state, "2026-10-05", "16:00", targets)
        self.assertEqual(pending, ["linkedin", "threads"])
        self.assertFalse(ledger.is_slot_fully_published(state, "2026-10-05", "16:00", targets))

        # Record failure for linkedin
        ledger.record_platform_status(
            state, "2026-10-05", "16:00", "linkedin",
            PublishResult(platform="linkedin", success=False, error="Rate limit", verified=False),
            path=self.test_state_file,
        )
        pending = ledger.get_pending_platforms(state, "2026-10-05", "16:00", targets)
        self.assertEqual(pending, ["linkedin", "threads"])

        # Record success for linkedin and threads
        ledger.record_platform_status(
            state, "2026-10-05", "16:00", "linkedin",
            PublishResult(platform="linkedin", success=True, url="https://linkedin.com/1", verified=True),
            path=self.test_state_file,
        )
        ledger.record_platform_status(
            state, "2026-10-05", "16:00", "threads",
            PublishResult(platform="threads", success=True, url="https://threads.net/1", verified=True),
            path=self.test_state_file,
        )

        self.assertEqual(ledger.get_pending_platforms(state, "2026-10-05", "16:00", targets), [])
        self.assertTrue(ledger.is_slot_fully_published(state, "2026-10-05", "16:00", targets))


if __name__ == "__main__":
    unittest.main()
