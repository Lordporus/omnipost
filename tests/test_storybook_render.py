"""Golden and regression tests for the 9:16 storybook card renderer.

Protects the phase-15 contract: 1080x1920 (2160x3840 at 2x) geometry, topic-
derived slides, offline-embedded fonts, readiness-based capture, and hard
failure when an asset cannot be produced.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from render import cards
from render.cards import (
    CARD_HEIGHT,
    CARD_WIDTH,
    build_card_slides,
    generate_topic_cards,
    render_card_html,
)
from scripts.errors import RenderError
from scripts.repurpose import repurpose_topic
from tests.copy_fixtures import rich_topic

TOPIC_A = {
    "headline": "Postgres 17 latency",
    "body": "The planner changes how distributed joins are costed across shards.",
    "points": [
        "Lower latency on distributed joins",
        "Better plans for skewed data",
        "Fewer retries under contention",
    ],
    "takeaway": "Measure the planner before tuning indexes.",
    "category": "DATABASE INTERNALS",
    "url": "https://example.com/postgres-17",
}

TOPIC_B = {
    "headline": "Kubernetes autoscaling",
    "body": "Horizontal pod autoscaling reacts to load with a delay that causes thrash.",
    "points": [
        "Stabilization windows reduce flapping",
        "Custom metrics beat CPU heuristics",
        "Pod disruption budgets protect availability",
    ],
    "takeaway": "Tune the stabilization window before raising max replicas.",
    "category": "PLATFORM ENGINEERING",
    "url": "https://example.com/k8s-autoscaling",
}

LEGACY_HEADLINES = (
    "Engineering Implementation & Tradeoffs",
    "Deterministic State Architecture",
    "Production Reliability Checklist",
)


def _browser_ready() -> bool:
    from scripts import browser

    try:
        browser.ensure_chrome(wait=5)
        return browser.alive()
    except Exception:
        return False


def test_slide_dimensions(tmp_path):
    """1x renders 1080x1920 and 2x renders 2160x3840."""
    if os.environ.get("CI") and not _browser_ready():
        pytest.skip("no CDP browser available in CI")

    from PIL import Image

    one = generate_topic_cards(
        TOPIC_A, "dim_1x", output_dir=tmp_path, explicit_count=1, scale=1.0
    )
    two = generate_topic_cards(
        TOPIC_A, "dim_2x", output_dir=tmp_path, explicit_count=1, scale=2.0
    )

    with Image.open(one[0]) as img:
        assert img.size == (CARD_WIDTH, CARD_HEIGHT) == (1080, 1920)
    with Image.open(two[0]) as img:
        assert img.size == (CARD_WIDTH * 2, CARD_HEIGHT * 2) == (2160, 3840)


def test_template_is_9_16():
    """Template is a 9:16 canvas with no remote font dependency."""
    src = (Path(cards.__file__).parent / "card_template.html").read_text(encoding="utf-8")
    assert "1080px" in src and "1920px" in src
    assert "fonts.googleapis.com" not in src
    assert "fonts.gstatic.com" not in src
    assert "{{FONT_CSS}}" in src
    for token in ("{{SOURCE}}", "{{TIMESTAMP}}", "{{PAGE_LABEL}}"):
        assert token in src


def test_two_topics_differ():
    """Two topics produce different, internally-unique slides."""
    a = build_card_slides(TOPIC_A, 3)
    b = build_card_slides(TOPIC_B, 3)

    assert [s["headline"] for s in a] != [s["headline"] for s in b]
    assert [s["body"] for s in a] != [s["body"] for s in b]

    for slides in (a, b):
        bodies = [s["body"] for s in slides]
        assert len(bodies) == len(set(bodies))
        bullet_sets = [tuple(s["bullets"]) for s in slides]
        assert len(bullet_sets) == len(set(bullet_sets))


def test_hardcoded_slides_removed():
    """The old generic slide headlines must not return."""
    src = Path(cards.__file__).read_text(encoding="utf-8")
    for legacy in LEGACY_HEADLINES:
        assert legacy not in src


def test_thin_topic_raises():
    """A topic that cannot supply distinct slides raises instead of inventing copy."""
    with pytest.raises(RenderError):
        build_card_slides({"headline": "Only a headline"}, 3)


def test_offline_render():
    """Rendered HTML embeds fonts and references no remote assets."""
    slide = build_card_slides(TOPIC_A, 2)[0]
    html = render_card_html(slide, current_idx=0, total_count=2, author="@test")

    assert "data:font/woff2;base64" in html
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_embedded_font_css_present():
    """All three vendored faces are embedded, so rendering needs no network."""
    from render.cards import _font_css

    css = _font_css()
    assert 'font-family: "Geist"' in css
    assert 'font-family: "Geist Mono"' in css
    assert css.count("data:font/woff2;base64,") == 3
    assert "https://" not in css


def test_no_fixed_sleep():
    """Capture must wait on readiness, not a fixed sleep."""
    src = Path(cards.__file__).read_text(encoding="utf-8")
    assert "asyncio.sleep(1.2)" not in src
    assert "document.fonts.ready" in src


def test_failure_blocks_draft(monkeypatch):
    """A render failure propagates out of repurpose_topic instead of falling back."""
    def boom(**kwargs):
        raise RenderError("capture_failed")

    monkeypatch.setattr("render.cards.generate_topic_cards", boom)

    with pytest.raises(RenderError):
        repurpose_topic(rich_topic(), generate_media=True)

def test_taste_design_palette_and_no_neon():
    """Card template adheres to /taste-design rules: no neon glows, no purple washes, clean slate canvas."""
    slide = build_card_slides(TOPIC_A, 1)[0]
    html = render_card_html(slide, current_idx=0, total_count=1, author="@Lordporus")

    # Anti-patterns from DESIGN.md
    assert "rgba(139, 92, 246" not in html, "Found banned purple radial glow"
    assert "box-shadow: 0 0 18px" not in html, "Found banned neon glowing drop-shadow"
    assert "box-shadow: 0 0 12px" not in html, "Found banned neon panel pulse"
    assert "THE CONTEXT" not in html, "Found generic AI boilerplate tag"

    # Positive taste tokens
    assert "--bg-canvas: #090D16" in html or "--bg-canvas: #0D1117" in html
    assert "brand-badge" in html or "[OP]" in html or "brand-tag" in html


def test_architecture_and_code_widgets_rendering():
    """Topic with architectural flow or code tokens synthesizes structured widgets instead of generic text."""
    topic_flow = {
        "headline": "Zero-Knowledge Rollup Architecture",
        "body": "Prover nodes generate SNARK proofs while sequencers batch state transitions.",
        "points": [
            "[Client] -> [Sequencer] -> [Prover Pool] -> [L1 Contract]",
            "Provers run parallel FFT kernels across GPU nodes.",
            "Batch verification settles on Ethereum in a single transaction.",
        ],
        "takeaway": "Decouple state sequencing from SNARK generation.",
        "category": "ZK ARCHITECTURE",
        "url": "https://example.com/zk-rollups",
    }
    slides = build_card_slides(topic_flow, 2)
    html = render_card_html(slides[1], current_idx=1, total_count=2, author="@Lordporus")
    assert "arch-flow" in html or "arch-node" in html or "terminal-window" in html

def test_header_author_deduplication_and_no_repeated_brand():
    """Card header must not repeat brand name when author string contains '• OmniPost'."""
    slide = build_card_slides(TOPIC_A, 1)[0]
    html = render_card_html(slide, current_idx=0, total_count=1, author="@Lordporus • OmniPost")

    # Brand name is OmniPost, so handle should be @Lordporus and NOT repeat OmniPost
    assert "OmniPost @Lordporus • OmniPost" not in html
    assert "@Lordporus" in html
    assert "• OmniPost" not in html


def test_header_title_bar_alignment_and_chip_geometry():
    """Header chips must use cohesive 8px border radii and matching heights for clean alignment."""
    slide = build_card_slides(TOPIC_A, 1)[0]
    html = render_card_html(slide, current_idx=0, total_count=1, author="@Lordporus")

    # Anti-pattern: 999px oval capsule pill clashing with rectangular chips
    assert "border-radius: 999px" not in html
    assert "border-radius: 8px" in html

