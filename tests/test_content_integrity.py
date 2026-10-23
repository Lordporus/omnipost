"""Phase 11 content-integrity and relevance-gate regression tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.errors import DuplicateTopic, NoRelevantTopic, TopicRejected
from scripts.generate import (
    bullet_fingerprint,
    content_fingerprint,
    generate_topic_from_items,
)
from scripts.pipeline import populate_daily_plan
from scripts.relevance import score_candidates, score_item
from scripts.repurpose import format_linkedin, format_threads


ENGINEERING_ITEM = {
    "source": "hn",
    "title": "Postgres 17 improves distributed query latency",
    "url": "https://example.com/postgres-latency",
    "score": 420,
    "extra": (
        "The database planner now handles distributed joins with lower latency. "
        "Teams can reduce query latency by using better statistics and avoiding "
        "unnecessary distributed scans."
    ),
}


def test_political_headline_rejected():
    item = {
        "title": "Jared Kushner Hacked Phone Reveals Secret Negotiations",
        "summary": "Politics and election coverage from Washington.",
    }
    result = score_item(item)
    assert result.accepted is False
    assert any(reason.startswith("blocklist:") for reason in result.reasons)


def test_engineering_headline_accepted():
    result = score_item(ENGINEERING_ITEM)
    assert result.accepted is True
    assert result.score >= 2
    assert "postgres" in result.matched_terms


def test_voice_profile_alignment():
    matching = score_item(
        ENGINEERING_ITEM,
        voice_profile="postgres database latency distributed systems",
    )
    assert matching.accepted is True
    assert matching.voice_alignment > 0

    blocked = score_item(
        {
            "title": "Celebrity election interview",
            "summary": "A politics story with no engineering substance.",
        },
        voice_profile="politics election celebrity",
    )
    assert blocked.accepted is False
    assert blocked.voice_alignment == 0


def test_all_candidates_scored():
    political = {"title": "President election results", "summary": "Politics."}
    results = score_candidates([political, ENGINEERING_ITEM])
    assert len(results) == 2
    assert results[0][1].accepted is False
    assert results[1][1].accepted is True


def test_llm_fallback_is_gated(monkeypatch):
    monkeypatch.setattr(
        "scripts.llm.generate_topic_with_llm",
        lambda **kwargs: (False, None),
    )
    topic = generate_topic_from_items("value", [ENGINEERING_ITEM])
    assert topic["headline"]
    assert score_item(
        {"title": topic["headline"], "summary": topic["body"]}
    ).accepted is True

    off_topic = {
        "headline": "Celebrity gossip roundup",
        "body": "A story about movies and music.",
        "points": ["Celebrity news", "Movie reviews", "Music charts"],
        "takeaway": "Celebrity news",
    }
    monkeypatch.setattr(
        "scripts.llm.generate_topic_with_llm",
        lambda **kwargs: (True, off_topic),
    )
    regated = generate_topic_from_items("value", [ENGINEERING_ITEM])
    assert regated["headline"] != off_topic["headline"]
    assert score_item(
        {"title": regated["headline"], "summary": regated["body"]}
    ).accepted is True


def test_empty_items_rejected():
    with pytest.raises(NoRelevantTopic):
        generate_topic_from_items("value", [], use_llm=False)


def test_title_only_item_raises():
    item = {
        "title": "Kubernetes distributed database latency architecture",
        "score": 100,
    }
    with pytest.raises(TopicRejected) as exc:
        generate_topic_from_items("value", [item], use_llm=False)
    assert exc.value.reason == "missing_summary"


def test_two_topics_produce_different_bullets():
    second = {
        "source": "rss",
        "title": "Rust compiler improves incremental build reliability",
        "url": "https://example.com/rust-compiler",
        "score": 300,
        "extra": (
            "The Rust compiler now caches incremental build artifacts more reliably. "
            "This reduces rebuild latency and improves developer throughput on large codebases."
        ),
    }
    first_topic = generate_topic_from_items("value", [ENGINEERING_ITEM], use_llm=False)
    second_topic = generate_topic_from_items("value", [second], use_llm=False)
    assert first_topic["points"] != second_topic["points"]
    assert set(first_topic["points"]).isdisjoint(set(second_topic["points"]))


def test_takeaway_never_domain():
    topic = generate_topic_from_items("value", [ENGINEERING_ITEM], use_llm=False)
    takeaway = topic["takeaway"].lower()
    assert "example.com" not in takeaway
    assert "verified reference" not in takeaway
    assert topic["takeaway"] in topic["points"]


def test_linkedin_has_no_hardcoded_boilerplate():
    text = format_linkedin(
        "Why Docker is weird",
        "A practical production note about container runtimes.",
        ["Relying on host networking hides port conflicts", "Pin the runtime version"],
        "Test the runtime boundary before scaling.",
        media_type="image",
    )
    assert "What changes in practice:" in text
    assert "▸ Relying on host networking" in text
    assert "Bottom line: Test the runtime boundary" in text
    assert "Matters in Production" not in text
    assert "Architectural Bottleneck" not in text
    assert "Production Principles to Remember" not in text
    assert "cards below" not in text
    assert "See the visual breakdown above." in text


def test_threads_has_no_verified_reference_or_state_drift():
    text = format_threads(
        "Why local inference is getting practical",
        "Paying OpenAI for every token is no longer the default choice.",
    )
    assert "Paying OpenAI for every token" in text
    assert "Verified Reference" not in text
    assert "state drift and unverified retry loops" not in text.lower()
    assert text.rstrip().endswith("?")


def test_duplicate_bullet_set_rejected():
    first = {
        "headline": "First headline",
        "points": ["same one", "same two", "same three"],
    }
    second = {
        "headline": "Second headline",
        "points": ["same three", "same one", "same two"],
    }
    assert content_fingerprint(first) == content_fingerprint(second)
    assert bullet_fingerprint(first) == bullet_fingerprint(second)

    plan = {
        "date": "2026-10-24",
        "slots": [
            {"slot": "13:00", "kind": "value", "text": ""},
            {"slot": "16:00", "kind": "value", "text": ""},
        ],
    }
    topic = {
        "headline": "Same topic",
        "body": "Same body",
        "points": ["same one", "same two", "same three"],
        "takeaway": "same three",
    }
    poly = {
        "x": {"text": "X text", "media": [], "enabled": True},
        "bluesky": {"text": "Bsky text", "media": [], "enabled": True},
        "linkedin": {"text": "LinkedIn text", "media": [], "enabled": True},
        "threads": {"text": "Threads text", "media": [], "enabled": True},
    }
    with patch("scripts.generate.generate_topic_from_items", return_value=topic), patch(
        "scripts.repurpose.repurpose_topic", return_value=poly
    ):
        with pytest.raises((NoRelevantTopic, DuplicateTopic)):
            populate_daily_plan(plan, [{"title": "candidate"}], force=True)


def test_generic_fallback_sentence_absent():
    source = Path("scripts/generate.py").read_text(encoding="utf-8")
    assert "Analyzing architectural tradeoffs" not in source
    assert "fallback_defaults" not in source
