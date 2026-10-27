"""Fix 6: do_post must not overwrite a ledger write made while it was publishing."""
import scripts.ledger as ledger
import scripts.post as post


def _seed(target, markers):
    ledger.save_state(
        {
            "version": ledger.CURRENT_SCHEMA_VERSION,
            "handle": "test",
            "ai_update_day": 0,
            "posts": [{"marker": m} for m in markers],
        },
        target,
    )


def _markers(target):
    return [p.get("marker") for p in ledger.load_state(target)["posts"]]


def test_record_post_keeps_concurrent_write(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    monkeypatch.setattr(post, "STATE", target)
    _seed(target, ["A"])
    # A second process publishes slot 16:00 and saves while this one is still running.
    _seed(target, ["A", "B"])

    post._record_post({"marker": "C", "at": "2026-10-27T09:00:00+00:00"}, "value", None, None)

    assert _markers(target) == ["A", "B", "C"]


def test_unverified_ai_update_does_not_consume_the_day(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    monkeypatch.setattr(post, "STATE", target)
    _seed(target, [])

    post._record_post(
        {"marker": "C", "at": "2026-10-27T09:00:00+00:00"}, "ai_update", None, 7
    )

    state = ledger.load_state(target)
    assert state["ai_update_day"] == 0
    assert state["posts"][-1]["note"].startswith("NOT counted")
