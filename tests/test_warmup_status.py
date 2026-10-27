"""Fix 4: the warm-up cap must count the status the ledger actually writes."""
import unittest
from datetime import datetime, timezone

from scripts import ledger
from scripts.validator import check_account_warmup


def _state(status: str) -> dict:
    return {
        "posts": [
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "slot": "13:00",
                "platforms": {"x": {"status": status}},
            }
        ]
    }


class TestWarmupCountsVerifiedPosts(unittest.TestCase):
    def test_published_verified_counts_toward_daily_cap(self):
        allowed, reason = check_account_warmup(_state(ledger.STATUS_PUBLISHED_VERIFIED),
                                               max_posts_per_day=1, platform="x")
        self.assertFalse(allowed, f"cap should have fired, got: {reason}")

    def test_legacy_published_status_still_counts(self):
        allowed, reason = check_account_warmup(_state("published"),
                                               max_posts_per_day=1, platform="x")
        self.assertFalse(allowed, f"legacy status should still count, got: {reason}")

    def test_failed_post_does_not_count(self):
        allowed, _ = check_account_warmup(_state(ledger.STATUS_FAILED),
                                          max_posts_per_day=1, platform="x")
        self.assertTrue(allowed, "a failed post must not consume the daily cap")


if __name__ == "__main__":
    unittest.main()
