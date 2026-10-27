"""Fix 2: X must confirm previews exist and refuse to submit without them."""
import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import post


class _Page:
    """Minimal CDP page whose composer reports a fixed preview count."""

    def __init__(self, media_count: int, uploading: bool = False):
        self.media_count = media_count
        self.uploading = uploading

    async def send(self, method, **kwargs):
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 1}}
        if method == "DOM.querySelector":
            return {"nodeId": 2}
        if method == "DOM.setFileInputFiles":
            return {}
        raise AssertionError(f"unexpected CDP method {method}")

    async def eval(self, js):
        return json.dumps({
            "btn_found": True,
            "btn_disabled": False,
            "media_count": self.media_count,
            "uploading": self.uploading,
        })


class TestXAttachVerification(unittest.TestCase):
    def _attach(self, page, paths):
        with patch.object(post, "ATTACH_POLLS", 2), \
             patch.object(post, "ATTACH_POLL_INTERVAL", 0):
            return asyncio.run(post._attach_images(page, paths))

    def test_no_preview_means_failure(self):
        # The old code returned "attached" here because the Post button was
        # already enabled by the typed text.
        status = self._attach(_Page(media_count=0), [Path("card.png")])
        self.assertTrue(status.startswith("fail:"), status)
        self.assertIn("0/1", status)

    def test_matching_preview_count_means_success(self):
        status = self._attach(_Page(media_count=1), [Path("card.png")])
        self.assertEqual(status, "attached:1")

    def test_partial_upload_is_a_failure(self):
        status = self._attach(_Page(media_count=1), [Path("a.png"), Path("b.png")])
        self.assertEqual(status, "fail:partial:1/2")

    def test_preview_present_but_still_uploading_is_a_failure(self):
        status = self._attach(_Page(media_count=1, uploading=True), [Path("card.png")])
        self.assertEqual(status, "fail:uploading")


if __name__ == "__main__":
    unittest.main()
