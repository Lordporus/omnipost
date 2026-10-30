"""Regression tests for the Threads hydration gate and trigger retry.

The 2026-10-27 failure clicked the composer before Threads had hydrated; the click
was swallowed and the run reported "button not found", which was the wrong story.
"""
import json
import unittest
from unittest.mock import AsyncMock, patch

from adapters.base import PublishPayload
from adapters.threads import (
    FOCUS_EDITOR_JS,
    HYDRATED_JS,
    SUBMIT_CONFIRMED_JS,
    SUBMIT_POST_JS,
    THREADS_PERMALINK_JS,
    TRIGGER_COMPOSER_JS,
    ThreadsAdapter,
)

LOADING = json.dumps({"loading": True, "button": True})
READY = json.dumps({"loading": False, "button": True})
NO_EDITOR = json.dumps({"status": "no_editor"})


class FakePage:
    """Dispatches on the exact JS constant the adapter passes to eval()."""

    def __init__(self, hydration, focus_failures):
        self._hydration = list(hydration)
        self._focus_failures = focus_failures
        self._focus_calls = 0
        self.kinds = []

    async def eval(self, expr):
        if expr == HYDRATED_JS:
            self.kinds.append("hydration")
            return self._hydration.pop(0) if len(self._hydration) > 1 else self._hydration[0]
        if expr == TRIGGER_COMPOSER_JS:
            self.kinds.append("trigger")
            return "clicked"
        if expr == FOCUS_EDITOR_JS:
            self.kinds.append("focus")
            self._focus_calls += 1
            return "focused" if self._focus_calls > self._focus_failures else NO_EDITOR
        if expr == SUBMIT_POST_JS:
            self.kinds.append("submit")
            return json.dumps({"clicked": True})
        if expr == SUBMIT_CONFIRMED_JS:
            self.kinds.append("confirm")
            return json.dumps({"editor_open": False, "posted": True})
        if expr == THREADS_PERMALINK_JS:
            self.kinds.append("permalink")
            return "https://www.threads.net/@lordporus_ai/post/ABC123"
        self.kinds.append("other")
        return None

    async def send(self, *args, **kwargs):
        return {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


class TestThreadsHydration(unittest.TestCase):
    def setUp(self):
        self.adapter = ThreadsAdapter(port=9444, handle="lordporus_ai")

    def _publish(self, page):
        with patch("adapters.threads.asyncio.sleep", new_callable=AsyncMock), \
             patch("scripts.browser.settle_page", new_callable=AsyncMock), \
             patch("adapters.threads.ThreadsAdapter._open_stealth", return_value=page), \
             patch("scripts.browser.ensure_chrome"):
            return self.adapter.publish(PublishPayload(text="Hydration test post"))

    def test_trigger_is_not_touched_while_the_page_is_loading(self):
        page = FakePage([LOADING, LOADING, LOADING, READY], focus_failures=0)
        res = self._publish(page)

        self.assertTrue(res.success)
        self.assertEqual(page.kinds[:4], ["hydration"] * 4)
        self.assertEqual(page.kinds[4], "trigger")
        self.assertEqual(page.kinds.count("trigger"), 1)

    def test_fails_with_hydration_stage_when_the_page_never_loads(self):
        page = FakePage([LOADING], focus_failures=0)
        res = self._publish(page)

        self.assertFalse(res.success)
        self.assertNotIn("trigger", page.kinds)

    def test_trigger_is_retried_when_the_composer_never_opens(self):
        # 20 focus polls per attempt; the first two attempts never focus.
        page = FakePage([READY], focus_failures=40)
        res = self._publish(page)

        self.assertTrue(res.success)
        self.assertEqual(page.kinds.count("trigger"), 3)


if __name__ == "__main__":
    unittest.main()
