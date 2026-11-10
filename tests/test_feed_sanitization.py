"""Tests for feed boundary metadata sanitization (arXiv, HN, and CMS signatures)."""
from __future__ import annotations

import pytest
from scripts.research import clean_swipe_bank, sanitize_feed_text, sanitize_item


def test_sanitize_arxiv_announcement_header() -> None:
    raw = (
        "arXiv:2610.37830v1 [cs.AI] Announce Type: new Abstract: "
        "Multi-agent systems encounter Byzantine failures in decentralized verification."
    )
    expected = "Multi-agent systems encounter Byzantine failures in decentralized verification."
    assert sanitize_feed_text(raw) == expected


def test_sanitize_arxiv_simple_abstract_header() -> None:
    raw = "arXiv:2401.12345v2 Abstract: We present an empirical evaluation of latency in state channels."
    expected = "We present an empirical evaluation of latency in state channels."
    assert sanitize_feed_text(raw) == expected


def test_sanitize_arxiv_no_version_header() -> None:
    raw = "arXiv:2305.99999 Announce Type: replace Abstract: New bounds on transaction propagation."
    expected = "New bounds on transaction propagation."
    assert sanitize_feed_text(raw) == expected


def test_sanitize_hn_metadata_tail() -> None:
    raw = (
        "A deep dive into distributed consensus protocols. "
        "Article URL: https://example.com/consensus Comments URL: https://news.ycombinator.com/item?id=123 Points: 250"
    )
    expected = "A deep dive into distributed consensus protocols."
    assert sanitize_feed_text(raw) == expected


def test_sanitize_techcrunch_syndication_tail() -> None:
    raw = (
        "AI chip architectures shift to memory-centric designs. "
        "The post AI chip architectures appeared first on TechCrunch."
    )
    expected = "AI chip architectures shift to memory-centric designs."
    assert sanitize_feed_text(raw) == expected


def test_sanitize_html_tags_and_entities() -> None:
    raw = "<p>Analyzing <b>throughput</b> &amp; latency in &quot;Raft&quot; clusters.</p>"
    expected = 'Analyzing throughput & latency in "Raft" clusters.'
    assert sanitize_feed_text(raw) == expected


def test_sanitize_clean_text_remains_intact() -> None:
    clean = "Postgres 17 introduces improved logical replication slots."
    assert sanitize_feed_text(clean) == clean


LEGACY_ITEM = {
    "source": "rss",
    "title": "Measuring Where Intent Gets Lost",
    "url": "https://arxiv.org/abs/2610.37830",
    "score": 0,
    "comments": 0,
    "created": "2026-10-25T00:00:00Z",
    "extra": {
        "feed": "arxiv-cs-ai",
        "summary": (
            "arXiv:2610.37830v1 Announce Type: new Abstract: "
            "AI agents can now write software from a plain-English description."
        ),
    },
}


def test_sanitize_item_cleans_nested_extra_and_keeps_metadata() -> None:
    cleaned = sanitize_item(dict(LEGACY_ITEM))
    assert "arXiv:" not in cleaned["extra"]["summary"]
    assert "Announce Type:" not in cleaned["extra"]["summary"]
    assert cleaned["extra"]["summary"].startswith("AI agents can now write software")
    assert cleaned["extra"]["feed"] == "arxiv-cs-ai"
    assert cleaned["url"] == LEGACY_ITEM["url"]


def test_sanitize_item_returns_a_copy() -> None:
    original = dict(LEGACY_ITEM)
    cleaned = sanitize_item(original)
    assert cleaned is not original
    assert original["extra"]["summary"] == LEGACY_ITEM["extra"]["summary"]


def test_load_daily_swipe_sanitizes_legacy_files(tmp_path, monkeypatch) -> None:
    import json

    from scripts import generate

    monkeypatch.setattr(generate, "ROOT", tmp_path)
    (tmp_path / "swipe").mkdir()
    (tmp_path / "swipe" / "2026-10-25.json").write_text(
        json.dumps([LEGACY_ITEM]), encoding="utf-8"
    )
    items = generate.load_daily_swipe("2026-10-25")
    assert items[0]["extra"]["summary"].startswith("AI agents can now write software")


def test_clean_swipe_bank_dry_run_changes_nothing(tmp_path) -> None:
    import json

    path = tmp_path / "2026-10-25.json"
    path.write_text(json.dumps([LEGACY_ITEM]), encoding="utf-8")
    before = path.read_bytes()
    summary = clean_swipe_bank(tmp_path, apply=False)
    assert summary["files"] == 1
    assert summary["files_changed"] == 1
    assert summary["markers_before"] >= 2
    assert summary["applied"] is False
    assert path.read_bytes() == before


def test_clean_swipe_bank_apply_is_idempotent(tmp_path) -> None:
    import json

    path = tmp_path / "2026-10-25.json"
    path.write_text(json.dumps([LEGACY_ITEM]), encoding="utf-8")
    clean_swipe_bank(tmp_path, apply=True)
    assert "arXiv:" not in path.read_text(encoding="utf-8")
    assert "Announce Type:" not in path.read_text(encoding="utf-8")
    second = clean_swipe_bank(tmp_path, apply=True)
    assert second["markers_before"] == 0
    assert second["items_changed"] == 0


def test_clean_swipe_bank_skips_malformed_file(tmp_path) -> None:
    import json

    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "2026-10-25.json").write_text(json.dumps([LEGACY_ITEM]), encoding="utf-8")
    summary = clean_swipe_bank(tmp_path, apply=True)
    assert summary["skipped"] == ["broken.json"]
    assert summary["files_changed"] == 1
    assert (tmp_path / "broken.json").read_text(encoding="utf-8") == "{ not json"
