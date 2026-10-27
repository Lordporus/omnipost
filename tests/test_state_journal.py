"""Fix 5: state writes must survive the Docker single-file bind mount."""
import errno
import json
from pathlib import Path

import scripts.ledger as ledger


def _state(slot: str) -> dict:
    return {
        "version": ledger.CURRENT_SCHEMA_VERSION,
        "handle": "test",
        "posts": [{"slot": slot, "at": "2026-10-27T09:00:00+00:00"}],
    }


def test_save_survives_ebusy_on_target(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    real_replace = ledger.os.replace

    def fake_replace(src, dst, *args, **kwargs):
        if Path(dst) == target:
            raise OSError(errno.EBUSY, "Device or resource busy")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(ledger.os, "replace", fake_replace)

    ledger.save_state(_state("09:00"), target)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["posts"][0]["slot"] == "09:00"
    assert not (tmp_path / "state.json.next").exists()
    assert not list(tmp_path.glob("state.json.tmp.*"))


def test_load_state_promotes_complete_journal(tmp_path):
    target = tmp_path / "state.json"
    target.write_text(json.dumps(_state("stale")), encoding="utf-8")
    journal = tmp_path / "state.json.next"
    journal.write_text(json.dumps(_state("newest")), encoding="utf-8")

    state = ledger.load_state(target)

    assert state["posts"][0]["slot"] == "newest"
    assert not journal.exists()
    assert json.loads(target.read_text(encoding="utf-8"))["posts"][0]["slot"] == "newest"


def test_load_state_discards_torn_journal(tmp_path):
    target = tmp_path / "state.json"
    target.write_text(json.dumps(_state("intact")), encoding="utf-8")
    journal = tmp_path / "state.json.next"
    journal.write_text('{"posts": [', encoding="utf-8")

    state = ledger.load_state(target)

    assert state["posts"][0]["slot"] == "intact"
    assert not journal.exists()
