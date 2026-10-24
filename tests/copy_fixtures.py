"""Shared rich-copy fixtures for the Phase 14 limit tests."""
from __future__ import annotations

from scripts.platform_limits import fit

RICH_HEADLINE = "Browser Automation Over DevTools Protocol Eliminates $200/mo API Bills"
RICH_TAKEAWAY = "Build sovereign developer tools before subscribing to cloud middleware."
RICH_BODY = " ".join(
    [
        "Running browser automation over direct DevTools Protocol websockets eliminates third-party SaaS middleman fees and unifies cross-posting.",
        "Deterministic state transitions make every publish observable, retryable, and safe to reconcile after a timeout.",
        "A single local control plane keeps credentials, media, and ledger state under the operator's control.",
        "Word-boundary truncation preserves readable copy while respecting each platform's real counting rule.",
        "Grapheme counting keeps emoji and combining sequences from silently overflowing Bluesky.",
        "Explicit media contracts prevent a PDF carousel from being advertised when only PNG cards are attached.",
        "Each platform receives its own copy length target instead of a single generic post.",
        "The dispatch layer is the final guard and records an undersized post as a failure rather than trimming it.",
        "A requeue path lets the pipeline try the next candidate when a topic cannot support the minimum length.",
        "Tests cover CJK, emoji, long words, media precedence, and idempotent failures.",
        "The result is a reproducible content pipeline with no hidden network calls in the copy layer.",
        "Operators can inspect the measured count for every platform before a live publish.",
    ]
)
RICH_POINTS = [
    "Direct WebSocket transport bypasses Selenium and Playwright bloat while keeping the real browser session.",
    "Page.printToPDF renders native vector carousels locally in about 400ms without a paid rendering service.",
    "Read-back profile inspection verifies published post state without relying on a third-party API.",
]

NATIVE_SEED = (
    "Native platform copy keeps deterministic state, local control, and readable "
    "observable publishing behavior. "
)


def rich_topic(**overrides):
    topic = {
        "headline": RICH_HEADLINE,
        "body": RICH_BODY,
        "points": list(RICH_POINTS),
        "takeaway": RICH_TAKEAWAY,
        "category": "DISTRIBUTED SYSTEMS",
    }
    topic.update(overrides)
    return topic


def valid_text(platform: str, seed: str = NATIVE_SEED) -> str:
    """Return a seed repeated enough to fit the platform's target range."""
    repeats = {
        "x": 10,
        "bluesky": 10,
        "threads": 30,
        "linkedin": 100,
    }[platform]
    return fit(platform, (seed * repeats).strip())
