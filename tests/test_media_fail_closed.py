"""Fix 3: LinkedIn and Threads must report attach failure instead of posting text-only."""
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from adapters.linkedin import LinkedInAdapter
from adapters.threads import ThreadsAdapter


async def _no_sleep(*_args, **_kwargs):
    return None


class _Page:
    """Composer page that accepts the file but never shows a preview."""

    def __init__(self, eval_result: str):
        self.eval_result = eval_result

    async def send(self, method, **kwargs):
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 1}}
        if method == "DOM.querySelector":
            return {"nodeId": 2}
        if method == "DOM.setFileInputFiles":
            return {}
        raise AssertionError(f"unexpected CDP method {method}")

    async def eval(self, js):
        return self.eval_result


class TestMediaFailClosed(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.image = Path(self.tmp.name) / "card.png"
        self.image.write_bytes(b"\x89PNG\r\n\x1a\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_linkedin_reports_failure_when_dialog_never_advances(self):
        adapter = LinkedInAdapter()
        with patch("asyncio.sleep", new=_no_sleep):
            attached = asyncio.run(
                adapter._attach_images(_Page("not_found"), [self.image])
            )
        self.assertFalse(attached, "LinkedIn must not claim a failed upload succeeded")

    def test_threads_reports_failure_when_no_preview_appears(self):
        adapter = ThreadsAdapter()
        with patch("asyncio.sleep", new=_no_sleep):
            attached = asyncio.run(
                adapter._attach_media(_Page("0"), [self.image])
            )
        self.assertFalse(attached, "Threads must not claim a failed upload succeeded")


if __name__ == "__main__":
    unittest.main()
