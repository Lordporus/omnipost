"""Integration tests for Polymorphic Multi-Platform Adaptation in OmniPost.

Validates that a single core research topic/insight is cleanly repurposed
into 4 platform-specific formats with strict adherence to platform constraints:
1. X (Twitter): <= 280 characters, punchy hook, concise bullet points
2. Bluesky: <= 300 characters, technical depth, correct UTF-8 byte facet calculations
3. LinkedIn: Detailed case study, structured key engineering takeaways, carousel CTA
4. Meta Threads: <= 500 characters, conversational framing, interactive hook
"""
from __future__ import annotations

import pytest

from adapters.bluesky import extract_facets
from scripts.repurpose import (
    format_bluesky,
    format_linkedin,
    format_threads,
    format_x,
    repurpose_topic,
)


@pytest.fixture
def core_insight():
    return {
        "headline": "Browser Automation Over DevTools Protocol Eliminates $200/mo API Bills",
        "body": "Modern platforms like X and LinkedIn charge enterprise rates for automation APIs that throttle creators. By controlling local headless Chrome over CDP websockets, sovereign developers retain 100% control with zero recurring SaaS costs.",
        "points": [
            "Direct WebSocket transport bypasses Selenium and Playwright bloat",
            "Page.printToPDF renders native vector carousels locally in 400ms",
            "Read-back profile inspection verifies published post state without paid APIs",
        ],
        "takeaway": "Build sovereign developer tools before subscribing to cloud middleware.",
        "category": "DISTRIBUTED SYSTEMS",
    }


def test_multiplatform_repurpose_simultaneous_invariants(core_insight):
    """Verify that repurposing a single insight generates valid outputs for all 4 platforms simultaneously."""
    adapted = repurpose_topic(core_insight, generate_media=False)

    assert "x" in adapted
    assert "bluesky" in adapted
    assert "linkedin" in adapted
    assert "threads" in adapted

    # 1. X Invariants
    x_slot = adapted["x"]
    assert x_slot["enabled"] is True
    assert len(x_slot["text"]) <= 280
    assert "• Direct WebSocket" in x_slot["text"] or "Browser Automation" in x_slot["text"]

    # 2. Bluesky Invariants
    bsky_slot = adapted["bluesky"]
    assert bsky_slot["enabled"] is True
    assert len(bsky_slot["text"]) <= 300
    assert "(1)" in bsky_slot["text"]

    # 3. LinkedIn Invariants
    li_slot = adapted["linkedin"]
    assert li_slot["enabled"] is True
    assert li_slot["media_type"] == "carousel"
    assert "Key Engineering Takeaways:" in li_slot["text"]
    assert "▸ Direct WebSocket" in li_slot["text"]
    assert "Bottom line:" in li_slot["text"]
    assert "Swipe through the architecture carousel" in li_slot["text"]
    assert len(li_slot["text"]) > 250

    # 4. Threads Invariants
    th_slot = adapted["threads"]
    assert th_slot["enabled"] is True
    assert len(th_slot["text"]) <= 500
    assert "Build sovereign" in th_slot["text"] or "experience" in th_slot["text"]


def test_bluesky_richtext_facet_byte_offset_calculation():
    """Verify Bluesky RichText facets use exact UTF-8 byte offsets rather than character offsets.
    
    Multi-byte UTF-8 characters (like emojis or non-ASCII characters) take >1 byte.
    A naive char index breaks ATProto URL facet highlights.
    """
    # 🚀 is 4 bytes in UTF-8, but 1 character in Python
    text = "🚀 Explore the repo at https://github.com/Lordporus/omnipost now!"
    facets = extract_facets(text)

    assert len(facets) == 1
    facet = facets[0]
    byte_start = facet["index"]["byteStart"]
    byte_end = facet["index"]["byteEnd"]

    # Python character index of "https://github.com/Lordporus/omnipost"
    char_start = text.find("https://github.com/Lordporus/omnipost")
    char_end = char_start + len("https://github.com/Lordporus/omnipost")

    # In UTF-8 bytes: '🚀' is 4 bytes + ' ' (1) + 'Explore the repo at ' (19) = 24 bytes
    # Whereas char_start is 1 + 1 + 19 = 21 chars.
    text_bytes = text.encode("utf-8")
    extracted_url_bytes = text_bytes[byte_start:byte_end].decode("utf-8")

    assert byte_start > char_start
    assert extracted_url_bytes == "https://github.com/Lordporus/omnipost"
    assert facet["features"][0]["uri"] == "https://github.com/Lordporus/omnipost"


def test_boundary_truncation_with_extremely_long_insight():
    """Verify that unusually long inputs are safely truncated without breaking platform length limits."""
    long_headline = "A" * 350
    long_points = ["B" * 200, "C" * 200, "D" * 200]
    long_takeaway = "E" * 300

    # X: strictly <= 280
    x_out = format_x(long_headline, long_points)
    assert len(x_out) <= 280
    assert x_out.endswith("...")

    # Bluesky: strictly <= 300
    bsky_out = format_bluesky(long_headline, long_points)
    assert len(bsky_out) <= 300
    assert bsky_out.endswith("...")

    # Threads: strictly <= 500
    th_out = format_threads(long_headline, long_takeaway)
    assert len(th_out) <= 500
    assert th_out.endswith("...")


def test_minimal_insight_payload():
    """Verify formatters handle minimal payload (no bullets or empty takeaway) without errors."""
    minimal_hl = "Simple Architecture Note"
    
    x_res = format_x(minimal_hl, [])
    assert x_res == "Simple Architecture Note"
    assert len(x_res) <= 280

    bsky_res = format_bluesky(minimal_hl, [])
    assert bsky_res == "Simple Architecture Note"
    assert len(bsky_res) <= 300

    th_res = format_threads(minimal_hl, "")
    assert "Simple Architecture Note" in th_res
    assert len(th_res) <= 500
