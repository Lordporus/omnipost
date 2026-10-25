"""End-to-end acceptance tests for the overhaul verifier.

These tests are offline: no credentials, browser, network, or live post. They
exercise the same checks the operator runs before a controlled live drop.
"""
from __future__ import annotations

from scripts import ledger
from scripts import verify_overhaul as verifier


def test_verifier_dry_run_passes(tmp_path):
    result = verifier.run_checks(dry_run=True, work_dir=tmp_path)

    assert result["overall"] == "PASS"
    assert result["checks"]
    assert all(check["status"] == "PASS" for check in result["checks"])


def test_two_topics_differ(tmp_path):
    result = verifier.run_checks(dry_run=True, two_topic=True, work_dir=tmp_path)
    check = next(item for item in result["checks"] if item["name"] == "two_topic")
    assert check["status"] == "PASS"

    topic_a = verifier._topic_a()
    topic_b = verifier._topic_b()
    assert topic_a["points"] != topic_b["points"]
    assert topic_a["takeaway"] != topic_b["takeaway"]

    from render import cards

    headlines_a = [slide["headline"] for slide in cards.build_card_slides(topic_a, count=3)]
    headlines_b = [slide["headline"] for slide in cards.build_card_slides(topic_b, count=3)]
    assert headlines_a != headlines_b


def test_political_item_rejected(tmp_path):
    result = verifier.run_checks(dry_run=True, work_dir=tmp_path)
    check = next(item for item in result["checks"] if item["name"] == "relevance")

    assert check["status"] == "PASS"
    assert "political rejected" in check["detail"]
    assert verifier.relevance.score_item(verifier.POLITICAL_ITEM).accepted is False


def test_unverified_is_not_pass():
    unverified = [
        {"platform": "threads", "status": ledger.STATUS_SUBMITTED_UNVERIFIED},
    ]
    assert verifier._overall_from_platforms(unverified) == "UNVERIFIED"

    failed = unverified + [{"platform": "x", "status": ledger.STATUS_FAILED}]
    assert verifier._overall_from_platforms(failed) == "FAIL"

    verified = [{"platform": "x", "status": ledger.STATUS_PUBLISHED_VERIFIED}]
    assert verifier._overall_from_platforms(verified) == "PASS"


def test_repeat_run_skips(tmp_path):
    path = tmp_path / "state.json"
    key = "2026-01-01:09:00:x"

    assert ledger.reserve_idempotency(key, "x", path=path) is True
    assert ledger.reserve_idempotency(key, "x", path=path) is False

    state = ledger.load_state(path)
    ledger.record_platform_status(
        state,
        "2026-01-01",
        "09:00",
        "x",
        {"success": True, "verified": True, "url": "https://x.example/1"},
        text="verification",
        path=path,
    )
    assert ledger.reserve_idempotency(key, "x", path=path) is False


def test_timeout_no_duplicate(tmp_path):
    path = tmp_path / "timeout.json"
    key = "2026-01-01:10:00:threads"

    assert ledger.reserve_idempotency(key, "threads", path=path) is True
    # The worker timed out before recording a result; the pending reservation
    # must still block a second dispatch.
    assert ledger.reserve_idempotency(key, "threads", path=path) is False

    state = ledger.load_state(path)
    record = ledger.get_platform_status(state, "2026-01-01", "10:00", "threads")
    assert record["status"] == ledger.STATUS_PENDING

    # Reconciliation records the timeout once. A retry then requires an explicit
    # allow_failed flag, so no automatic retry can duplicate the post.
    ledger.record_platform_status(
        state,
        "2026-01-01",
        "10:00",
        "threads",
        {"success": False, "verified": False, "error": "timeout"},
        text="verification",
        path=path,
    )
    state = ledger.load_state(path)
    record = ledger.get_platform_status(state, "2026-01-01", "10:00", "threads")
    assert record["status"] == ledger.STATUS_FAILED
    assert ledger.reserve_idempotency(key, "threads", path=path) is False
    assert ledger.reserve_idempotency(key, "threads", path=path, allow_failed=True) is True


def test_report_columns(tmp_path):
    result = verifier.run_checks(dry_run=True, two_topic=True, work_dir=tmp_path)
    report = verifier.build_report(result, source="dry-run")
    lowered = report.lower()

    for column in ("status", "verified", "url", "content hash", "chars / limit", "dimensions"):
        assert column in lowered

    assert "Live evidence pending" in report
    assert "Overall verdict" in report
    assert "dry-run" in report


def test_no_live_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(verifier, "SCRATCH", tmp_path)
    called = {"run_live": False}

    def fail_if_called(*args, **kwargs):
        called["run_live"] = True
        raise AssertionError("_run_live must not be called without --confirm-live")

    monkeypatch.setattr(verifier, "_run_live", fail_if_called)

    assert verifier.main(["--live", "--slot", "09:00"]) == 2
    assert called["run_live"] is False

    captured = capsys.readouterr()
    assert "requires --confirm-live" in captured.err
