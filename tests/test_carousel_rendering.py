"""Integration tests for LinkedIn PDF Carousel Rendering in OmniPost V2.

Validates:
- Structured 4-slide parsing and zero headline duplication
- 1080x1080 CSS page size dimension locking in template HTML
- Vector PDF binary structure (valid %PDF magic header)
- LinkedIn document payload structure compatibility
"""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from adapters.base import PublishPayload
from render.carousel import (
    build_carousel_html,
    create_carousel_pdf,
    generate_standard_slides,
    parse_linkedin_payload,
)


def test_parse_linkedin_payload_extracts_clean_fields():
    """Verify topic parsing extracts non-overlapping semantic segments."""
    topic_data = {
        "headline": "Deterministic Agent Architectures",
        "body": "Production state machines eliminate dual-post bugs in high concurrency systems.",
        "points": [
            "▸ Atomic file replacement prevents corrupted state reads",
            "• Direct CDP socket communication bypasses cloud API costs",
            "1. Verified profile readback confirms live rendering",
        ],
        "takeaway": "Never rely on unverified LLM completions for production state.",
        "category": "SYSTEMS DESIGN",
    }

    parsed = parse_linkedin_payload(topic_data)
    assert parsed["headline"] == "Deterministic Agent Architectures"
    assert "Production state machines" in parsed["problem_context"]
    assert len(parsed["points"]) == 3
    # Verify bullet symbols were stripped
    assert not parsed["points"][0].startswith("▸")
    assert not parsed["points"][1].startswith("•")
    assert not parsed["points"][2].startswith("1.")
    assert parsed["takeaway"] == "Never rely on unverified LLM completions for production state."
    assert parsed["category"] == "SYSTEMS DESIGN"


def test_generate_standard_slides_structure_and_no_duplicate_headline():
    """Ensure standard 4-slide carousel layout maintains zero headline duplication."""
    raw_text = (
        "Zero-Cost Agent Scheduling Architecture\n\n"
        "Most autonomous agents burn $50/mo just polling APIs when nothing is due.\n"
        "Here is how a zero-cost gate script eliminates idle model invocation.\n\n"
        "Key Engineering Takeaways:\n"
        "▸ Deterministic due.py check yields byte-identical IDLE\n"
        "▸ Cron agent runner is suppressed unless work is waiting\n"
        "▸ Atomic state transition logs execution timestamps\n\n"
        "Bottom line: Stop paying for idle agent thinking loops.\n\n"
        "Swipe through the architecture carousel below for the complete breakdown ➔"
    )

    slides = generate_standard_slides(raw_text, author="@engineer • OmniPost")
    assert len(slides) == 4

    # Slide 1: Hero
    assert slides[0]["type"] == "hero"
    assert slides[0]["title"] == "Zero-Cost Agent Scheduling Architecture"

    # Slide 2: Problem
    assert slides[1]["type"] == "problem"
    assert "idle model invocation" in slides[1]["body"]
    assert slides[1]["title"] != slides[0]["title"]

    # Slide 3: Solution
    assert slides[2]["type"] == "solution"
    assert "code" in slides[2]
    assert "PublishingGate" in slides[2]["code"]

    # Slide 4: Checklist CTA
    assert slides[3]["type"] == "checklist_cta"
    assert "Stop paying for idle" in slides[3]["body"]
    assert len(slides[3]["bullets"]) >= 1


def test_build_carousel_html_enforces_1080x1080_viewport_scaling():
    """Verify HTML template embeds @page 1080px by 1080px rule to prevent blurred slides."""
    slides = [
        {"type": "hero", "title": "Slide 1", "body": "Overview", "tag": "TECH"},
        {"type": "solution", "title": "Slide 2", "body": "Details", "tag": "TECH"},
    ]
    html_doc = build_carousel_html(slides, title="Architecture Carousel", author="@Lordporus")

    assert "@page" in html_doc
    assert "1080px 1080px" in html_doc
    assert "Slide 1" in html_doc
    assert "Slide 2" in html_doc
    assert "@Lordporus" in html_doc
    assert "1 / 2" in html_doc
    assert "2 / 2" in html_doc


def test_create_carousel_pdf_binary_structure(tmp_path):
    """Verify generated PDF output starts with valid %PDF magic header bytes."""
    output_pdf = tmp_path / "test_deck.pdf"

    # Minimal valid PDF binary sample (%PDF-1.4 header + basic trailer)
    mock_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF"

    async def fake_render(html_file, output_pdf, port):
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        output_pdf.write_bytes(mock_pdf_bytes)
        return output_pdf

    with patch("render.carousel._render_pdf_cdp", side_effect=fake_render):
        slides = generate_standard_slides({
            "headline": "Sovereign Engineering Stack",
            "body": "Zero external dependencies beyond standard library and Chrome CDP.",
            "points": ["Rule 1", "Rule 2", "Rule 3"],
            "takeaway": "Simplicity is the prerequisite for reliability.",
        })
        result_path = create_carousel_pdf(slides, output_path=output_pdf)

        assert result_path == output_pdf
        assert output_pdf.exists()
        pdf_data = output_pdf.read_bytes()
        assert pdf_data.startswith(b"%PDF-")


def test_linkedin_document_publish_payload_compatibility(tmp_path):
    """Verify LinkedIn document upload payload schema matches adapter expectations."""
    pdf_path = tmp_path / "architecture.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake pdf data")

    payload = PublishPayload(
        text="A breakdown of modern sovereign publishing pipelines.",
        media_paths=[pdf_path],
        media_type="carousel",
        extra_metadata={"document_title": "OmniPost Architecture Blueprint"},
    )

    assert payload.media_type == "carousel"
    assert len(payload.media_paths) == 1
    assert payload.media_paths[0].suffix == ".pdf"
    assert payload.extra_metadata["document_title"] == "OmniPost Architecture Blueprint"
