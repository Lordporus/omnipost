"""Idempotency, timeout, and manual-publish tests for Phase 12."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from adapters.base import PlatformCapabilities, PublishPayload, PublishResult
from scripts import ledger, publish_now, publish_worker


class FakeAdapter:
    def __init__(self, name: str = "x"):
        self.platform_name = name
        self.capabilities = PlatformCapabilities(max_characters=1000)
        self.publish_calls: list[PublishPayload] = []
        self.verify_result = True
        self.session = {"ok": True, "handle": "tester"}

    def publish(self, payload: PublishPayload) -> PublishResult:
        self.publish_calls.append(payload)
        return PublishResult(
            platform=self.platform_name,
            success=True,
            verified=True,
            url=f"https://{self.platform_name}.example/post/1",
        )

    def verify(self, post_id, text: str) -> bool:
        return self.verify_result

    def check_session(self) -> dict:
        return dict(self.session)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _state_path(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "state.json"
    monkeypatch.setattr(ledger, "STATE_PATH", path)
    return path


_DEFAULT_DRAFT_TEXT = ("A deterministic idempotency test post. " * 7).strip()


def _draft(tmp_path, text: str = _DEFAULT_DRAFT_TEXT) -> Path:
    path = tmp_path / "draft.json"
    path.write_text(
        json.dumps({"slot": "13:00", "text": text}),
        encoding="utf-8",
    )
    return path


def _seed_status(
    state_path: Path,
    *,
    platform: str = "x",
    slot: str = "13:00",
    success: bool,
    verified: bool,
    error: str | None = None,
) -> str:
    date = _today()
    key = f"{date}:{slot}:{platform}"
    state = ledger.load_state(state_path)
    result = PublishResult(
        platform=platform,
        success=success,
        verified=verified,
        url=f"https://{platform}.example/post/1" if success else None,
        error=error,
    )
    ledger.record_platform_status(
        state,
        date,
        slot,
        platform,
        result,
        text="A deterministic idempotency test post.",
        path=state_path,
        idempotency_key=key,
    )
    return key


def _run_main(
    monkeypatch,
    draft_path: Path,
    *,
    extra_args: list[str] | None = None,
    adapters: list[FakeAdapter] | None = None,
    dispatch=None,
    online: bool = True,
):
    adapter = adapters[0] if adapters else FakeAdapter()
    monkeypatch.setattr(
        publish_now.settings,
        "get_active_adapters",
        lambda: adapters if adapters is not None else [adapter],
    )
    monkeypatch.setattr(publish_now, "check_connectivity", lambda **kwargs: online)
    monkeypatch.setattr(
        publish_now.notify_webhook,
        "dispatch_summary_card",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        publish_now.notify_webhook,
        "dispatch_webhook",
        lambda *args, **kwargs: True,
    )
    if dispatch is not None:
        monkeypatch.setattr(publish_now, "_dispatch_worker", dispatch)
    else:
        def fail_dispatch(*args, **kwargs):
            raise AssertionError("dispatch must not run")

        monkeypatch.setattr(publish_now, "_dispatch_worker", fail_dispatch)

    argv = ["publish_now.py", "--draft", str(draft_path)]
    argv.extend(extra_args or [])
    monkeypatch.setattr(sys, "argv", argv)
    return publish_now.main(), adapter


def test_duplicate_manual_publish_skipped(tmp_path, monkeypatch):
    state_path = _state_path(tmp_path, monkeypatch)
    _seed_status(state_path, success=True, verified=True)
    draft = _draft(tmp_path)

    code, adapter = _run_main(monkeypatch, draft)

    assert code == 0
    assert adapter.publish_calls == []
    state = ledger.load_state(state_path)
    record = ledger.get_platform_status(state, _today(), "13:00", "x")
    assert record["status"] == ledger.STATUS_PUBLISHED_VERIFIED


def test_force_publish_overrides(tmp_path, monkeypatch):
    state_path = _state_path(tmp_path, monkeypatch)
    _seed_status(state_path, success=True, verified=True)
    draft = _draft(tmp_path)
    calls: list[int] = []

    def dispatch(adapter, payload, timeout):
        calls.append(1)
        return PublishResult(
            platform="x",
            success=True,
            verified=True,
            url="https://x.example/post/2",
        )

    code, adapter = _run_main(
        monkeypatch,
        draft,
        extra_args=["--force"],
        dispatch=dispatch,
    )

    assert code == 0
    assert calls == [1]
    assert adapter.publish_calls == []
    state = ledger.load_state(state_path)
    record = ledger.get_platform_status(state, _today(), "13:00", "x")
    assert record["status"] == ledger.STATUS_PUBLISHED_VERIFIED
    assert record["attempt"] == 2


def test_timeout_reconciles_before_failure(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.killed = False
            self.calls = 0
            self.returncode = -9

        def communicate(self, input=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("worker", timeout)
            return "", ""

        def kill(self):
            self.killed = True

    adapter = FakeAdapter("threads")
    adapter.verify_result = True
    first = FakeProcess()
    monkeypatch.setattr(
        publish_now.subprocess,
        "Popen",
        lambda *args, **kwargs: first,
    )

    verified = publish_now._dispatch_worker(
        adapter,
        PublishPayload(text="hello world"),
        timeout=0.01,
    )

    assert first.killed is True
    assert verified.success is True
    assert verified.verified is True
    assert verified.error is None

    adapter.verify_result = False
    second = FakeProcess()
    monkeypatch.setattr(
        publish_now.subprocess,
        "Popen",
        lambda *args, **kwargs: second,
    )

    unverified = publish_now._dispatch_worker(
        adapter,
        PublishPayload(text="hello world"),
        timeout=0.01,
    )

    assert second.killed is True
    assert unverified.success is True
    assert unverified.verified is False
    assert unverified.error == "timeout_unreconciled"


def test_timeout_does_not_duplicate(tmp_path, monkeypatch):
    state_path = _state_path(tmp_path, monkeypatch)
    _seed_status(state_path, success=True, verified=False, error="timeout_unreconciled")
    draft = _draft(tmp_path)

    code, adapter = _run_main(monkeypatch, draft)

    assert code == 3
    assert adapter.publish_calls == []
    state = ledger.load_state(state_path)
    record = ledger.get_platform_status(state, _today(), "13:00", "x")
    assert record["status"] == ledger.STATUS_SUBMITTED_UNVERIFIED


def test_concurrent_reservation_only_one_wins(tmp_path, monkeypatch):
    _state_path(tmp_path, monkeypatch)
    key = "2026-10-24:13:00:x"
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def reserve() -> None:
        barrier.wait(timeout=5)
        results.append(ledger.reserve_idempotency(key, "x"))

    threads = [threading.Thread(target=reserve) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(results) == 2
    assert sum(results) == 1
    state = ledger.load_state()
    record = ledger.get_idempotency_record(state, key)
    assert record is not None
    assert record["status"] == ledger.STATUS_PENDING
    assert record["attempt"] == 1


def test_failed_retry_requires_flag(tmp_path, monkeypatch):
    state_path = _state_path(tmp_path, monkeypatch)
    _seed_status(state_path, success=False, verified=False, error="rate limited")
    draft = _draft(tmp_path)
    calls: list[int] = []

    def dispatch(adapter, payload, timeout):
        calls.append(1)
        return PublishResult(
            platform="x",
            success=True,
            verified=True,
            url="https://x.example/post/3",
        )

    code_without_flag, _ = _run_main(
        monkeypatch,
        draft,
        dispatch=dispatch,
    )
    assert code_without_flag == 1
    assert calls == []

    code_with_flag, _ = _run_main(
        monkeypatch,
        draft,
        extra_args=["--retry-failed"],
        dispatch=dispatch,
    )
    assert code_with_flag == 0
    assert calls == [1]
    state = ledger.load_state(state_path)
    record = ledger.get_platform_status(state, _today(), "13:00", "x")
    assert record["status"] == ledger.STATUS_PUBLISHED_VERIFIED
    assert record["attempt"] == 2


def test_offline_returns_two(tmp_path, monkeypatch):
    state_path = _state_path(tmp_path, monkeypatch)
    draft = _draft(tmp_path)

    code, adapter = _run_main(monkeypatch, draft, online=False)

    assert code == 2
    assert adapter.publish_calls == []
    assert not state_path.exists()


def test_dry_run_writes_no_state(tmp_path, monkeypatch):
    state_path = _state_path(tmp_path, monkeypatch)
    draft = _draft(tmp_path)
    adapter = FakeAdapter("bluesky")

    monkeypatch.setattr(
        publish_now.settings,
        "get_active_adapters",
        lambda: [adapter],
    )
    monkeypatch.setattr(
        publish_now,
        "check_connectivity",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not probe connectivity")
        ),
    )
    monkeypatch.setattr(
        publish_now,
        "_dispatch_worker",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not dispatch")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["publish_now.py", "--draft", str(draft), "--dry-run"],
    )

    code = publish_now.main()

    assert code == 0
    assert adapter.publish_calls == []
    assert not state_path.exists()


def test_pending_reservation_not_overwritten(tmp_path, monkeypatch):
    _state_path(tmp_path, monkeypatch)
    key = "2026-10-24:13:00:x"

    assert ledger.reserve_idempotency(key, "x") is True
    assert ledger.reserve_idempotency(key, "x") is False

    state = ledger.load_state()
    record = ledger.get_idempotency_record(state, key)
    assert record is not None
    assert record["status"] == ledger.STATUS_PENDING
    assert record["attempt"] == 1


def test_worker_result_file_contract(tmp_path, monkeypatch, capsys):
    result_file = tmp_path / "worker-result.json"
    payload = {
        "platform": "x",
        "text": "worker contract",
        "media_paths": [],
        "media_type": "image",
        "extra_metadata": {},
    }
    adapter = FakeAdapter("x")

    def noisy_publish(publish_payload):
        print("adapter-noise")
        return PublishResult(
            platform="x",
            success=True,
            verified=True,
            url="https://x.example/post/1",
        )

    adapter.publish = noisy_publish
    monkeypatch.setattr(
        publish_worker.settings,
        "get_active_adapters",
        lambda: [adapter],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(
        sys,
        "argv",
        ["publish_worker.py", "--result-file", str(result_file)],
    )

    code = publish_worker.main()

    assert code == 0
    assert result_file.exists()
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["platform"] == "x"
    assert data["success"] is True
    assert data["verified"] is True
    assert data["url"] == "https://x.example/post/1"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "adapter-noise" in captured.err
