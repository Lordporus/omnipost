"""Fix 1: autoposter must publish through the killable worker, not in-process."""
import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from adapters.base import PlatformCapabilities, PublishResult
from scripts import autoposter, ledger


class _Adapter:
    """Records accidental in-process publishes; they are the bug."""

    def __init__(self, name: str):
        self.platform_name = name
        self.capabilities = PlatformCapabilities(max_characters=1000)
        self.publish_calls = 0

    def publish(self, payload):
        self.publish_calls += 1
        raise AssertionError("autoposter must not call adapter.publish in-process")


class TestAutoposterUsesWorker(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.state_file = Path(self.tmp.name) / "state.json"
        self.today = datetime.now().strftime("%Y-%m-%d")

    def tearDown(self):
        self.tmp.cleanup()

    def _due_item(self) -> dict:
        return {
            "date": self.today,
            "slot": "14:00",
            "kind": "value",
            "text": "worker dispatch test",
            "platforms": {"x": {"enabled": True}},
        }

    def _run(self, worker_result: PublishResult, due_item: dict | None = None):
        adapter = _Adapter("x")
        with patch.object(ledger, "STATE_PATH", self.state_file), \
             patch("scripts.autoposter.ledger.STATE_PATH", self.state_file), \
             patch("scripts.autoposter.ensure_daily_plan"), \
             patch("scripts.autoposter.run_cmd", return_value=(0, json.dumps(due_item or self._due_item()))), \
             patch("scripts.autoposter.settings.get_active_adapters", return_value=[adapter]), \
             patch("scripts.autoposter.settings.load", return_value={}), \
             patch("scripts.autoposter.notify.notify_publish"), \
             patch("scripts.autoposter._dispatch_worker", return_value=worker_result) as worker, \
             patch("sys.argv", ["autoposter.py"]):
            code = autoposter.main()
        return code, worker, adapter

    def test_publishes_through_worker_with_timeout(self):
        code, worker, adapter = self._run(
            PublishResult(platform="x", success=True, verified=True, url="https://x.com/u/1")
        )
        self.assertEqual(code, 0)
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(worker.call_args.args[0], adapter)
        self.assertEqual(worker.call_args.args[2], 120.0)
        self.assertEqual(adapter.publish_calls, 0)

    def test_worker_failure_is_recorded_as_failed(self):
        code, worker, adapter = self._run(
            PublishResult(platform="x", success=False, verified=False, error="boom")
        )
        self.assertEqual(code, 1)
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(adapter.publish_calls, 0)
        st = ledger.load_state(self.state_file)
        self.assertFalse(ledger.is_platform_done(st, self.today, "14:00", "x"))

    def test_missing_requested_media_prevents_dispatch(self):
        present = Path(self.tmp.name) / "card.png"
        present.write_bytes(b"card")
        missing = Path(self.tmp.name) / "missing.png"
        directory = Path(self.tmp.name) / "directory.png"
        directory.mkdir()

        for media in ([missing], [present, missing], [directory]):
            with self.subTest(media=media):
                item = self._due_item()
                item["platforms"]["x"]["media"] = list(map(str, media))
                # Each case gets an independent reservation and ledger entry.
                item["slot"] = f"media-{len(media)}-{media[0].name}"
                code, worker, _ = self._run(
                    PublishResult(platform="x", success=True, verified=True), item,
                )

                self.assertEqual(code, 1)
                worker.assert_not_called()
                state = ledger.load_state(self.state_file)
                status = ledger.get_platform_status(state, self.today, item["slot"], "x")
                self.assertEqual(status["status"], ledger.STATUS_FAILED)
                self.assertIn("Requested media files not found", status["error"])
                self.assertIn(str(media[-1]), status["error"])

    def test_existing_requested_media_reaches_worker_in_order(self):
        paths = [Path(self.tmp.name) / name for name in ("first.png", "second.png")]
        for path in paths:
            path.write_bytes(b"card")
        item = self._due_item()
        item["platforms"]["x"]["media"] = list(map(str, paths))

        code, worker, _ = self._run(
            PublishResult(platform="x", success=True, verified=True, url="https://x.com/u/1"), item,
        )

        self.assertEqual(code, 0)
        self.assertEqual(worker.call_args.args[1].media_paths, paths)


if __name__ == "__main__":
    unittest.main()
