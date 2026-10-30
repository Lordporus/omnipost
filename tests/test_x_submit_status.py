"""A submitted X post must never be recorded as a retryable failure.

X's toast only renders after the platform accepts the post. If the profile
readback misses it, the run is ``submitted_unverified`` (terminal), never
``failed`` - ``failed`` is retryable and would post the same text twice.
"""
from __future__ import annotations

from unittest.mock import patch

import adapters.x as ax
from adapters.base import PublishPayload
from adapters.x import XAdapter
from scripts import ledger

PAYLOAD = PublishPayload(text="A" * 250)


def _do_post_result(**overrides):
    base = {
        "posted": False,
        "verified": False,
        "toast_sent": False,
        "error": None,
        "tweet_url": None,
        "day": None,
        "screenshot": "s.png",
        "profile_screenshot": None,
        "profile_head": [],
    }
    base.update(overrides)
    return base


def _publish(**overrides):
    with patch.object(ax.post, "do_post", return_value=_do_post_result(**overrides)):
        return XAdapter().publish(PAYLOAD)


def _status(result) -> str:
    state = {"posts": []}
    ledger._record_platform_status_locked(
        state, "2026-10-30", "13:00", "x", result, text=PAYLOAD.text
    )
    return state["posts"][0]["platforms"]["x"]["status"]


def test_toast_without_readback_is_submitted_unverified():
    result = _publish(toast_sent=True)

    assert result.success is True
    assert result.verified is False
    assert _status(result) == ledger.STATUS_SUBMITTED_UNVERIFIED


def test_no_toast_and_no_readback_is_a_real_failure():
    result = _publish()

    assert result.success is False
    assert _status(result) == ledger.STATUS_FAILED


def test_readback_match_is_published_verified():
    result = _publish(
        posted=True,
        verified=True,
        toast_sent=True,
        tweet_url="https://x.com/Lordporus/status/1",
    )

    assert _status(result) == ledger.STATUS_PUBLISHED_VERIFIED
