"""Task 1: X composer writes must target the modal, not the background feed composer.

`x.com/compose/post` mounts the modal a beat after the feed, so the page can hold
two composers. Every write path is now dialog-only: if the modal is absent the
call fails closed instead of touching the feed's inline composer.
"""
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import post


async def _no_sleep(*_args, **_kwargs):
    return None


class _Page:
    """Fake CDP session that records selectors and dispatched events."""

    def __init__(self, node_id=42, pos=None):
        self.node_id = node_id
        self.pos = pos
        self.selectors = []
        self.set_files = []
        self.inserted = []
        self.mouse = []

    async def send(self, method, **kwargs):
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 1}}
        if method == "DOM.querySelector":
            self.selectors.append(kwargs["selector"])
            return {"nodeId": self.node_id}
        if method == "DOM.setFileInputFiles":
            self.set_files.append(kwargs)
            return {}
        if method == "Input.insertText":
            self.inserted.append(kwargs.get("text"))
            return {}
        if method == "Input.dispatchMouseEvent":
            self.mouse.append(kwargs)
            return {}
        raise AssertionError(f"unexpected CDP method {method}")

    async def eval(self, js):
        if "getBoundingClientRect" in js:
            return self.pos
        return ('{"btn_disabled": false, "media_count": 1, "uploading": false, '
                '"editor_text": "typed", "has_editor": true}')


class TestXDialogScope(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.image = Path(self.tmp.name) / "card.png"
        self.image.write_bytes(b"\x89PNG\r\n\x1a\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_attach_uses_dialog_scoped_input_only(self):
        page = _Page(node_id=42)
        with patch("asyncio.sleep", new=_no_sleep):
            status = asyncio.run(post._attach_images(page, [self.image]))
        self.assertEqual(status, "attached:1")
        self.assertEqual(page.selectors, [f"{post.DIALOG} {post.FILE_INPUT}"])
        self.assertEqual(page.set_files[0]["nodeId"], 42)

    def test_missing_dialog_input_fails_closed(self):
        page = _Page(node_id=0)
        with patch("asyncio.sleep", new=_no_sleep):
            status = asyncio.run(post._attach_images(page, [self.image]))
        self.assertEqual(status, "no-file-input")
        self.assertEqual(page.set_files, [])

    def test_insert_text_reads_back_through_compose_state(self):
        page = _Page()
        with patch("asyncio.sleep", new=_no_sleep):
            got = asyncio.run(post._insert_text(page, "hello"))
        self.assertEqual(page.inserted, ["hello"])
        self.assertEqual(got, "typed")

    def test_click_post_refuses_without_dialog(self):
        page = _Page(pos=None)
        with patch("asyncio.sleep", new=_no_sleep):
            result = asyncio.run(post._click_post(page))
        self.assertEqual(result, "no-dialog")
        self.assertEqual(page.mouse, [])

    def test_composer_js_requires_dialog(self):
        for js in (post.FOCUS_JS, post.COMPOSE_READY_JS, post.COMPOSE_STATE_JS):
            self.assertIn('[role="dialog"]', js)
            self.assertNotIn("|| document", js)

    def test_uploading_ignores_permanent_progressbar_stub(self):
        # X keeps a role="progressbar" in the composer at all times; treating it
        # as an upload signal made every image post fail with fail:uploading.
        self.assertNotIn('role="progressbar"', post.COMPOSE_STATE_JS)
        self.assertIn("naturalWidth", post.COMPOSE_STATE_JS)


class _ComposePage:
    """Minimal page for do_post: dialog ready, nothing to screenshot."""

    async def eval(self, js):
        if js == post.COMPOSE_READY_JS:
            return "ready"
        if js == "location.href":
            return "https://x.com/compose/post"
        return ""

    async def send(self, *_args, **_kwargs):
        return {}

    async def __aexit__(self, *_exc):
        return None


class TestXTextGuard(unittest.TestCase):
    def test_value_post_fails_when_the_body_did_not_land(self):
        # X allows image-only posts, so an insert that misses the dialog would
        # publish media with no text unless the body is verified.
        page = _ComposePage()

        async def _open(_url):
            return page

        async def _login(_page):
            return {"logged_in": True, "handle": ""}

        async def _insert(_page, _text):
            return ""

        async def _settle(*_args, **_kwargs):
            return None

        with patch.multiple(
            post,
            cfg=lambda: {},
            load_state=lambda: {},
            handle=lambda: "",
            validate_draft_guardrails=lambda **_kw: None,
            _open=_open,
            wait_login=_login,
            _insert_text=_insert,
        ), patch("scripts.browser.ensure_chrome"), \
           patch("scripts.browser.settle_page", new=_settle):
            with self.assertRaises(SystemExit) as raised:
                asyncio.run(post.do_post("hello world", dry_run=True))

        self.assertIn("text did not land", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
