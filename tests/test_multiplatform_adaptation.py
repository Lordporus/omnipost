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
from scripts.errors import CopyValidationError
from scripts.platform_limits import LIMITS, count_for
from scripts.repurpose import (
    format_bluesky,
    format_linkedin,
    format_threads,
    format_x,
    repurpose_topic,
)
from tests.copy_fixtures import rich_topic


@pytest.fixture
def core_insight():
    return rich_topic()


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
    assert LIMITS["x"]["min"] <= count_for("x", x_slot["text"]) <= LIMITS["x"]["hard_max"]
    assert "• Direct WebSocket" in x_slot["text"] or "Browser Automation" in x_slot["text"]

    # 2. Bluesky Invariants
    bsky_slot = adapted["bluesky"]
    assert bsky_slot["enabled"] is True
    assert (
        LIMITS["bluesky"]["min"]
        <= count_for("bluesky", bsky_slot["text"])
        <= LIMITS["bluesky"]["hard_max"]
    )
    assert "(1)" in bsky_slot["text"]

    # 3. LinkedIn Invariants
    li_slot = adapted["linkedin"]
    assert li_slot["enabled"] is True
    assert li_slot["media_type"] == "image"
    assert "document_title" not in li_slot
    assert "What changes in practice:" in li_slot["text"]
    assert "▸ Direct WebSocket" in li_slot["text"]
    assert "Bottom line:" in li_slot["text"]
    assert "Architectural Bottleneck" not in li_slot["text"]
    assert "cards below" not in li_slot["text"]
    assert (
        LIMITS["linkedin"]["min"]
        <= count_for("linkedin", li_slot["text"])
        <= LIMITS["linkedin"]["max"]
    )

    # 4. Threads Invariants
    th_slot = adapted["threads"]
    assert th_slot["enabled"] is True
    assert (
        LIMITS["threads"]["min"]
        <= count_for("threads", th_slot["text"])
        <= LIMITS["threads"]["hard_max"]
    )
    assert "Browser Automation" in th_slot["text"]
    assert th_slot["text"].rstrip().endswith("?")


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
    """Verify long inputs truncate on word boundaries without breaking limits."""
    long_headline = " ".join(["Architecture"] * 50)
    long_points = [
        " ".join(["Benchmark"] * 20),
        " ".join(["Observability"] * 20),
        " ".join(["Reliability"] * 20),
    ]
    long_takeaway = " ".join(["Deterministic"] * 30)

    # X: strictly <= 280, word-boundary ellipsis.
    x_out = format_x(long_headline, long_points)
    assert count_for("x", x_out) <= LIMITS["x"]["hard_max"]
    assert x_out.endswith("...")

    # Bluesky: strictly <= 300, word-boundary ellipsis.
    bsky_out = format_bluesky(long_headline, long_points)
    assert count_for("bluesky", bsky_out) <= LIMITS["bluesky"]["hard_max"]
    assert bsky_out.endswith("...")

    # Threads: strictly <= 500 and still ends on a discussion question.
    th_out = format_threads(long_headline, long_takeaway, points=long_points)
    assert count_for("threads", th_out) <= LIMITS["threads"]["hard_max"]
    assert th_out.endswith("?")


def test_minimal_insight_payload():
    """A topic too thin to meet the minimum is rejected, never padded."""
    minimal_hl = "Simple Architecture Note"

    with pytest.raises(CopyValidationError):
        format_x(minimal_hl, [])

    with pytest.raises(CopyValidationError):
        format_bluesky(minimal_hl, [])

    with pytest.raises(CopyValidationError):
        format_threads(minimal_hl, "")

    with pytest.raises(CopyValidationError):
        format_linkedin(minimal_hl, "Short body.", [], "Short takeaway.")
