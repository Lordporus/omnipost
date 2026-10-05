"""Unit tests for multi-platform configuration resolution and autoposter integration."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from adapters.base import PlatformCapabilities, PublishPayload, PublishResult
from scripts import autoposter, settings


class TestMultiPlatformSettings(unittest.TestCase):
    """Test suite for settings.get_platforms and backwards compatibility."""

    def test_legacy_config_backward_compatibility(self):
        legacy_cfg = {
            "handle": "LegacyUser",
            "premium": True,
            "max_chars": 10000,
        }
        platforms = settings.get_platforms(legacy_cfg)
        self.assertIn("x", platforms)
        self.assertTrue(platforms["x"]["enabled"])
        self.assertEqual(platforms["x"]["handle"], "LegacyUser")
        self.assertTrue(platforms["x"]["premium"])
        self.assertEqual(platforms["x"]["max_chars"], 10000)

    def test_multi_platform_config_resolution(self):
        multi_cfg = {
            "platforms": {
                "x": {"enabled": False},
                "bluesky": {
                    "enabled": True,
                    "identifier": "test.bsky.social",
                    "app_password": "secret_app_pw",
                },
            }
        }
        platforms = settings.get_platforms(multi_cfg)
        self.assertFalse(platforms["x"]["enabled"])
        self.assertTrue(platforms["bluesky"]["enabled"])
        self.assertEqual(platforms["bluesky"]["identifier"], "test.bsky.social")

    def test_get_active_adapters_filters_disabled(self):
        multi_cfg = {
            "platforms": {
                "x": {"enabled": False},
                "bluesky": {
                    "enabled": True,
                    "identifier": "active.bsky.social",
                    "app_password": "pw",
                },
            }
        }
        adapters = settings.get_active_adapters(multi_cfg)
        self.assertEqual(len(adapters), 1)
        self.assertEqual(adapters[0].platform_name, "bluesky")


class TestAutoposterMultiPlatform(unittest.TestCase):
    """Test suite for autoposter publishing across multiple adapters."""

    @patch("scripts.autoposter.ensure_daily_plan")
    @patch("scripts.autoposter.run_cmd")
    @patch("scripts.settings.get_active_adapters")
    def test_autoposter_dispatches_to_all_active_adapters(
        self, mock_get_adapters, mock_run_cmd, mock_plan
    ):
        # Setup due check output
        mock_run_cmd.side_effect = [
            (0, '{"slot": "14:00", "kind": "value", "text": "Cross-platform test"}'),
            (0, "marked"),
        ]

        # Setup mock adapters
        mock_x = MagicMock()
        mock_x.platform_name = "x"
        mock_x.capabilities = PlatformCapabilities(max_characters=280)
        mock_x.publish.return_value = PublishResult(
            platform="x", success=True, url="https://x.com/post/1", verified=True
        )

        mock_bsky = MagicMock()
        mock_bsky.platform_name = "bluesky"
        mock_bsky.capabilities = PlatformCapabilities(max_characters=300)
        mock_bsky.publish.return_value = PublishResult(
            platform="bluesky", success=True, url="https://bsky.app/post/2", verified=True
        )

        mock_get_adapters.return_value = [mock_x, mock_bsky]

        with patch("sys.argv", ["autoposter.py"]):
            code = autoposter.main()

        self.assertEqual(code, 0)
        self.assertEqual(mock_x.publish.call_count, 1)
        self.assertEqual(mock_bsky.publish.call_count, 1)


if __name__ == "__main__":
    unittest.main()
