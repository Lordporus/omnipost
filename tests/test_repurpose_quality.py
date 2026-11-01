"""Tests for copy deduplication and dynamic formatting in LinkedIn and Threads."""
from __future__ import annotations

import pytest
from scripts.repurpose import format_linkedin, format_threads, _is_similar


def test_is_similar_detects_high_overlap() -> None:
    a = "Zero-knowledge verifiers reduce rollup latency by 40% under contention."
    b = "Zero-knowledge verifiers reduce rollup latency by 40% under high contention"
    assert _is_similar(a, b, threshold=0.6) is True


def test_is_similar_handles_dissimilar_text() -> None:
    a = "Zero-knowledge verifiers reduce rollup latency by 40% under contention."
    b = "Database connection pooling limits memory exhaustion during traffic spikes."
    assert _is_similar(a, b, threshold=0.6) is False


def test_linkedin_drops_duplicate_body_bullet() -> None:
    headline = "Why ZK Rollup Verification Latency Bottlenecks Layer-2 Throughput"
    dup_sentence = "Zero-knowledge verifiers reduce rollup latency by 40% under heavy block contention."
    body = (
        f"{dup_sentence} In production systems, batch proof generation dominates the critical path. "
        "When transaction volumes spike across decentralized sequencers, recursive proving architectures "
        "become mandatory to sustain target blocks per second without incurring quadratic verification overhead. "
        "Deterministic memory layouts prevent prover out-of-memory crashes on GPU clusters."
    )
    points = [
        dup_sentence,  # Duplicate of first sentence in body
        "Batch proofs amortize verification cost across 10,000 transactions.",
        "Prover timeouts require fallback fraud-proof windows.",
        "Recursive SNARK aggregation cuts finality times down to sub-second slots.",
    ]
    takeaway = "Rollups must decouple batch proving from real-time sequencing."

    text = format_linkedin(headline, body, points, takeaway)

    # The exact body sentence should not appear twice in the post
    count = text.count(dup_sentence)
    assert count == 1, f"Body was duplicated in bullets. Post:\n{text}"
    assert "Batch proofs amortize verification cost" in text


def test_linkedin_drops_duplicate_takeaway_bullet() -> None:
    headline = "Why Raft Distributed Consensus Fails Under Heavy Disk Sync Latency"
    body = (
        "Raft clusters encounter leader failover delays when disk sync latency spikes across storage volumes. "
        "Under sustained write pressure, fsync stalls prevent follower nodes from acknowledging append entries in time. "
        "This triggers split-brain elections that degrade client throughput across high-availability deployments. "
        "Proper write-ahead log partitioning is essential for stable production state machine replication."
    )
    points = [
        "Heartbeat timeouts trigger unneeded leader elections.",
        "WAL fsync stalls block client state progression.",
        "Decoupling commit logs from state machines restores throughput across all follower nodes.",
    ]
    # Takeaway is identical to the last bullet
    takeaway = "Decoupling commit logs from state machines restores throughput across all follower nodes."

    text = format_linkedin(headline, body, points, takeaway)

    count = text.count("Decoupling commit logs from state machines restores throughput across all follower nodes")
    assert count == 1, f"Takeaway was duplicated from bullet. Post:\n{text}"


def test_threads_removes_hardcoded_cta_and_redundant_bullets() -> None:
    headline = "Postgres 17 Query Optimization Architecture"
    dup_sentence = "Postgres 17 introduces memory-adaptive hash joins, reducing temp disk spill."
    body = (
        f"{dup_sentence} Analytical workloads frequently exceed work_mem limits, "
        "causing expensive spills to disk that bottleneck concurrent queries. Adaptive memory allocation "
        "dynamically reallocates buffer pool pages during complex join execution."
    )
    points = [
        dup_sentence,  # Duplicate of body
        "Work_mem boundaries adapt dynamically during large analytical scans across large tables.",
        "Query planners prioritize index scans when memory pressure is detected.",
    ]
    takeaway = "Analytical queries finish 3x faster without manual buffer tuning in production."

    text = format_threads(headline, takeaway=takeaway, body=body, points=points)

    # 1. Hardcoded CTA must NOT be present
    assert "What architectural tradeoffs have you seen in your stack?" not in text
    # 2. Body must not be echoed verbatim as a bullet
    assert text.count(dup_sentence) == 1
    # 3. Must be clean, informative copy within 350-480 target
    assert 350 <= len(text) <= 500
