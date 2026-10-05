"""Integration & unit tests for partial-failure isolation and retry engine."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from adapters.base import PlatformCapabilities, PublishPayload, PublishResult
from scripts import autoposter, ledger


class MockPlatformAdapter:
    def __init__(self, name: str, success: bool = True, url: str | None = None, error: str | None = None):
        self.platform_name = name
        self.success = success
        self.url = url or f"https://{name}.com/testpost"
        self.error = error
        self.capabilities = PlatformCapabilities(max_characters=1000)
        self.publish_calls = []

    def publish(self, payload: PublishPayload) -> PublishResult:
        self.publish_calls.append(payload)
        return PublishResult(
            platform=self.platform_name,
            success=self.success,
            url=self.url if self.success else None,
            verified=self.success,
            error=self.error,
        )


class TestPartialFailureRetryIsolation(unittest.TestCase):
    """Test suite ensuring failed platforms are retried while successful platforms are skipped."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.state_file = self.temp_path / "state.json"
        self.drafts_dir = self.temp_path / "drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

        self.today_str = datetime.now().strftime("%Y-%m-%d")
        self.plan_file = self.drafts_dir / f"{self.today_str}.json"

        # Create test daily plan with 1 slot
        self.plan_data = {
            "date": self.today_str,
            "slots": [
                {
                    "slot": "14:00",
                    "kind": "value",
                    "due_at": f"{self.today_str}T13:00:00",
                    "text": "Autonomous Agentic Architecture insight.",
                    "posted": False,
                    "platforms": {
                        "x": {"enabled": True},
                        "bluesky": {"enabled": True},
                        "linkedin": {"enabled": True},
                        "threads": {"enabled": True},
                    },
                }
            ],
        }
        self.plan_file.write_text(json.dumps(self.plan_data, indent=2), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("scripts.autoposter.ensure_daily_plan")
    @patch("scripts.autoposter.run_cmd")
    @patch("scripts.autoposter.settings.get_active_adapters")
    def test_partial_failure_and_subsequent_retry(
        self, mock_get_adapters, mock_run_cmd, mock_plan
    ):
        # Point autoposter and ledger STATE_PATH to self.state_file
        with patch.object(ledger, "STATE_PATH", self.state_file), \
             patch("scripts.autoposter.ledger.STATE_PATH", self.state_file):

            # First run: X, Bluesky, Threads succeed; LinkedIn fails with rate limit
            mock_x = MockPlatformAdapter("x", success=True)
            mock_bsky = MockPlatformAdapter("bluesky", success=True)
            mock_li = MockPlatformAdapter("linkedin", success=False, error="Cooldown: 4h limit")
            mock_thrd = MockPlatformAdapter("threads", success=True)

            mock_get_adapters.return_value = [mock_x, mock_bsky, mock_li, mock_thrd]

            due_item = {
                "date": self.today_str,
                "slot": "14:00",
                "kind": "value",
                "text": "Autonomous Agentic Architecture insight.",
                "platforms": self.plan_data["slots"][0]["platforms"],
            }

            mock_run_cmd.side_effect = [
                (0, json.dumps(due_item)),  # due check for round 1
            ]

            # Run first autoposter iteration (simulate due slot)
            with patch("sys.argv", ["autoposter.py"]):
                ret1 = autoposter.main()

            # Exit code should be 1 indicating partial completion
            self.assertEqual(ret1, 1)

            # Verify state ledger records
            st1 = ledger.load_state(self.state_file)
            self.assertTrue(ledger.is_platform_done(st1, self.today_str, "14:00", "x"))
            self.assertTrue(ledger.is_platform_done(st1, self.today_str, "14:00", "bluesky"))
            self.assertTrue(ledger.is_platform_done(st1, self.today_str, "14:00", "threads"))
            self.assertFalse(ledger.is_platform_done(st1, self.today_str, "14:00", "linkedin"))

            # Verify each adapter was called exactly once in round 1
            self.assertEqual(len(mock_x.publish_calls), 1)
            self.assertEqual(len(mock_bsky.publish_calls), 1)
            self.assertEqual(len(mock_thrd.publish_calls), 1)
            self.assertEqual(len(mock_li.publish_calls), 1)

            # Round 2: On subsequent tick, LinkedIn succeeds
            mock_x.publish_calls.clear()
            mock_bsky.publish_calls.clear()
            mock_thrd.publish_calls.clear()
            mock_li.publish_calls.clear()
            mock_li.success = True
            mock_li.error = None

            mock_run_cmd.side_effect = [
                (0, json.dumps(due_item)),  # due check for round 2
                (0, "marked"),              # due.py mark call
            ]

            with patch("sys.argv", ["autoposter.py"]):
                ret2 = autoposter.main()

            # Exit code should be 0 (all target platforms now successfully published)
            self.assertEqual(ret2, 0)

            # CRITICAL VERIFICATION: X, Bluesky, Threads were SKIPPED (0 publish calls)
            self.assertEqual(len(mock_x.publish_calls), 0, "X must not be published twice!")
            self.assertEqual(len(mock_bsky.publish_calls), 0, "Bluesky must not be published twice!")
            self.assertEqual(len(mock_thrd.publish_calls), 0, "Threads must not be published twice!")

            # Only LinkedIn was retried and succeeded
            self.assertEqual(len(mock_li.publish_calls), 1, "LinkedIn must be retried!")

            # Verify final state is completely published
            st2 = ledger.load_state(self.state_file)
            self.assertTrue(ledger.is_slot_fully_published(st2, self.today_str, "14:00", ["x", "bluesky", "linkedin", "threads"]))

        pass


if __name__ == "__main__":
    unittest.main()
