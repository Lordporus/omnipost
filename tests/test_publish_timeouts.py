"""Publish budgets must fit the readback they wait for.

The X readback now tolerates a 90s stale timeline. An 80s worker budget killed
it mid-read, and the post-timeout reconciliation ran unbounded on top of that.
"""
from __future__ import annotations

import time

from scripts import publish_now


def test_default_platform_timeout_fits_a_slow_readback():
    assert publish_now.DEFAULT_PLATFORM_TIMEOUT >= 150.0


def test_timeout_reconciliation_is_bounded():
    def slow_verify(*_args, **_kwargs):
        time.sleep(5)
        return True

    started = time.time()
    verified = publish_now._verify_with_budget(slow_verify, "text", budget=0.2)
    elapsed = time.time() - started

    assert verified is False
    assert elapsed < 2.0


def test_timeout_reconciliation_returns_the_verify_result():
    assert publish_now._verify_with_budget(lambda *_a: True, "text", budget=1.0) is True
