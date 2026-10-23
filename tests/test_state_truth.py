"""Truthful publish-state tests for the v3 ledger."""
from __future__ import annotations

import json
import threading
import time

import pytest

from adapters.base import PublishResult
from scripts import ledger
from scripts.errors import StateCorruptionError, StateLockTimeout


def _state_path(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(ledger, "STATE_PATH", path)
    return path


def test_unverified_is_not_published(tmp_path, monkeypatch):
    path = _state_path(tmp_path, monkeypatch)
    state = ledger.load_state()
    result = PublishResult(
        platform="threads",
        success=True,
        verified=False,
        url="https://threads.net/@alice/post/1",
    )

    ledger.record_platform_status(
        state,
        "2026-10-24",
        "13:00",
        "threads",
        result,
        text="A submitted but unverified post",
        idempotency_key="2026-10-24:13:00:threads",
    )

    record = ledger.get_platform_status(state, "2026-10-24", "13:00", "threads")
    assert record is not None
    assert record["status"] == ledger.STATUS_SUBMITTED_UNVERIFIED
    assert record["verified"] is False
    assert ledger.is_platform_done(state, "2026-10-24", "13:00", "threads") is False
    assert path.exists()


def test_verified_is_published(tmp_path, monkeypatch):
    _state_path(tmp_path, monkeypatch)
    state = ledger.load_state()
    result = PublishResult(
        platform="threads",
        success=True,
        verified=True,
        url="https://threads.net/@alice/post/2",
    )

    ledger.record_platform_status(
        state,
        "2026-10-24",
        "13:00",
        "threads",
        result,
        text="A verified post",
        idempotency_key="2026-10-24:13:00:threads",
    )

    record = ledger.get_platform_status(state, "2026-10-24", "13:00", "threads")
    assert record is not None
    assert record["status"] == ledger.STATUS_PUBLISHED_VERIFIED
    assert record["verified"] is True
    assert ledger.is_platform_done(state, "2026-10-24", "13:00", "threads") is True


def test_failure_is_failed(tmp_path, monkeypatch):
    _state_path(tmp_path, monkeypatch)
    state = ledger.load_state()
    result = PublishResult(
        platform="linkedin",
        success=False,
        verified=False,
        error="rate limited",
    )

    ledger.record_platform_status(
        state,
        "2026-10-24",
        "13:00",
        "linkedin",
        result,
        text="A failed post",
        idempotency_key="2026-10-24:13:00:linkedin",
    )

    record = ledger.get_platform_status(state, "2026-10-24", "13:00", "linkedin")
    assert record is not None
    assert record["status"] == ledger.STATUS_FAILED
    assert record["error"] == "rate limited"
    assert ledger.is_platform_done(state, "2026-10-24", "13:00", "linkedin") is False


def test_v2_migration():
    data = {
        "version": "2.0",
        "handle": "alice",
        "custom_field": "keep-me",
        "posts": [
            {
                "date": "2026-10-24",
                "slot": "13:00",
                "text": "verified legacy",
                "tweet_url": "https://x.com/alice/1",
                "verified": True,
                "platforms": {
                    "x": {
                        "status": "published",
                        "verified": True,
                        "url": "https://x.com/alice/1",
                        "extra": "keep-platform-field",
                    }
                },
            },
            {
                "date": "2026-10-24",
                "slot": "16:00",
                "text": "unverified legacy",
                "tweet_url": "https://x.com/alice/2",
                "verified": False,
                "platforms": {
                    "x": {
                        "status": "published",
                        "verified": False,
                        "url": "https://x.com/alice/2",
                    }
                },
            },
        ],
    }

    migrated = ledger.migrate_state(data)

    assert migrated["version"] == "3.0"
    assert migrated["migrated_from"] == "2.0"
    assert migrated["custom_field"] == "keep-me"

    first = migrated["posts"][0]
    assert first["tweet_url"] == "https://x.com/alice/1"
    assert first["verified"] is True
    assert first["platforms"]["x"]["status"] == ledger.STATUS_PUBLISHED_VERIFIED
    assert first["platforms"]["x"]["extra"] == "keep-platform-field"

    second = migrated["posts"][1]
    assert second["platforms"]["x"]["status"] == ledger.STATUS_SUBMITTED_UNVERIFIED


def test_corrupt_state_quarantined(tmp_path):
    path = tmp_path / "state.json"
    backup = tmp_path / "state.json.bak"
    path.write_text("{not valid json", encoding="utf-8")
    backup.write_text(
        json.dumps(
            {
                "version": "3.0",
                "handle": "backup-handle",
                "posts": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = ledger.load_state(path)

    assert loaded["handle"] == "backup-handle"
    assert list(tmp_path.glob("state.json.corrupt.*"))
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["handle"] == "backup-handle"


def test_empty_state_never_overwrites(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(StateCorruptionError):
        ledger.load_state(path)

    assert list(tmp_path.glob("state.json.corrupt.*"))
    assert not path.exists()


def test_lock_serializes_writers(tmp_path):
    path = tmp_path / "state.json"
    ledger.save_state({"version": "3.0", "posts": [], "count": 0}, path)

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def increment() -> None:
        try:
            barrier.wait(timeout=5)
            with ledger.state_transaction(path, timeout=5) as state:
                current = int(state.get("count", 0))
                time.sleep(0.1)
                state["count"] = current + 1
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=increment) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    loaded = ledger.load_state(path)
    assert loaded["count"] == 2


def test_lock_timeout_raises(tmp_path):
    path = tmp_path / "state.json"
    ledger.save_state({"version": "3.0", "posts": []}, path)

    ready = threading.Event()
    release = threading.Event()

    def hold_lock() -> None:
        with ledger.state_transaction(path, timeout=5):
            ready.set()
            release.wait(timeout=5)

    holder = threading.Thread(target=hold_lock)
    holder.start()
    assert ready.wait(timeout=5)

    try:
        with pytest.raises(StateLockTimeout):
            with ledger.state_transaction(path, timeout=0.05):
                pass
    finally:
        release.set()
        holder.join(timeout=5)
