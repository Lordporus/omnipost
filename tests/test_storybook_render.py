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
