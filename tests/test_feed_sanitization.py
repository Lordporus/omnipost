"""Tests for feed boundary metadata sanitization (arXiv, HN, and CMS signatures)."""
from __future__ import annotations

import pytest
from scripts.research import sanitize_feed_text


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
