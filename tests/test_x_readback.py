"""The X profile readback must poll for the post, not for any render.

Right after a send, X serves a cached profile timeline. The old readback
returned the first non-empty render, so a months-old post counted as "newest"
and a live post was reported as missing.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import scripts.post as post

STALE = [{"text": "months-old cached post", "url": "", "at": ""}]
FRESH = [{"text": "the new post we just made", "url": "https://x.com/a/status/1", "at": ""}]


class FakePage:
    def __init__(self, renders):
        self.renders = list(renders)
        self.reads = 0
        self.sent: list[str] = []

    async def eval(self, _js):
        render = self.renders[min(self.reads, len(self.renders) - 1)]
        self.reads += 1
        return json.dumps(render)

    async def send(self, method, **_params):
        self.sent.append(method)
        return {}

    async def __aexit__(self, *_args):
        return None


def _read(page, **kwargs):
    async def fake_open(_url):
        return page

    async def fake_settle(_page, _seconds):
        return None

    with patch.object(post, "_open", fake_open), \
         patch.object(post.browser, "settle_page", fake_settle):
        return asyncio.run(post._read_profile(**kwargs))


def test_waits_for_the_target_instead_of_the_first_render():
    page = FakePage([STALE, STALE, FRESH])

    rows = _read(page, target="the new post", wait=5.0, interval=0)

    assert rows[0]["text"] == "the new post we just made"
    assert page.reads == 3


def test_stale_render_is_not_returned_as_proof():
    page = FakePage([STALE])

    rows = _read(page, target="the new post", wait=0.05, interval=0.01)

    assert not any("the new post" in row["text"] for row in rows)


def test_forces_a_reload_when_the_render_stays_stale():
    page = FakePage([STALE] * 6 + [FRESH])

    rows = _read(page, target="the new post", wait=5.0, interval=0)

    assert rows[0]["text"] == "the new post we just made"
    assert "Page.reload" in page.sent
