"""Unit tests for the render.carousel HTML builder, payload parser, and CDP PDF exporter."""
import base64
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from render.carousel import (
    build_carousel_html,
    create_carousel_pdf,
    generate_standard_slides,
    parse_linkedin_payload,
)


class TestCarouselBuilder(unittest.TestCase):
    """Test suite for slide HTML compilation and PDF generation."""

    def test_build_carousel_html_single_slide(self):
        slides = [{
            "title": "Welcome to OmniPost V2",
            "body": "Cross-platform autonomous syndication pipeline.",
            "tag": "INTRO",
            "bullets": ["Zero API cost for X", "Native ATProto for Bluesky"],
        }]
        html_out = build_carousel_html(slides, title="Test Carousel", author="@Lordporus")

        self.assertIn("Welcome to OmniPost V2", html_out)
        self.assertIn("Cross-platform autonomous syndication pipeline.", html_out)
        self.assertIn("Zero API cost for X", html_out)
        self.assertIn("@Lordporus", html_out)
        self.assertIn("1 / 1", html_out)
        self.assertIn("Connect & Share", html_out)  # Last slide CTA
        self.assertIn("@page {", html_out)
        self.assertIn("1080px 1080px", html_out)

    def test_build_carousel_html_multiple_slides(self):
        slides = [
            {"title": "Slide 1 Hook", "body": "Intro text"},
            {"title": "Slide 2 Content", "bullets": ["Point A", "Point B"]},
            {"title": "Slide 3 Summary", "body": "Final takeaways"},
        ]
        html_out = build_carousel_html(slides, title="Multi Slide Test")

        self.assertIn("Slide 1 Hook", html_out)
        self.assertIn("1 / 3", html_out)
        self.assertIn("Swipe ➔", html_out)  # Early slide CTA
        self.assertIn("3 / 3", html_out)
        self.assertIn("Connect & Share", html_out)

    def test_create_carousel_pdf_empty_slides_raises(self):
        with self.assertRaises(ValueError):
            create_carousel_pdf([])

    @patch("render.carousel._render_pdf_cdp")
    def test_create_carousel_pdf_delegates_to_cdp(self, mock_render_cdp):
        fake_pdf = Path("scratch/test_carousel.pdf")

        async def fake_render(html_file, output_pdf, port):
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            output_pdf.write_bytes(b"%PDF-1.4 test vector pdf content")
            return output_pdf

        mock_render_cdp.side_effect = fake_render

        slides = [{"title": "Architecture", "body": "Overview"}]
        result = create_carousel_pdf(
            slides=slides,
            title="Architecture Deck",
            output_path=fake_pdf,
            port=9444,
        )

        self.assertEqual(result, fake_pdf)
        self.assertTrue(fake_pdf.exists())
        self.assertTrue(fake_pdf.read_bytes().startswith(b"%PDF-1.4"))
        if fake_pdf.exists():
            fake_pdf.unlink()

    def test_generate_standard_slides_structure(self):
        topic = {
            "headline": "Deterministic Agent Architectures",
            "body": "State machines guarantee zero dual-post bugs in high throughput systems.",
            "points": [
                "Atomic state transitions prevent duplicate dispatch.",
                "CDP socket bypasses expensive 3rd-party SaaS fees.",
                "Multi-platform polymorphism from a unified payload.",
            ],
            "takeaway": "Never rely on raw unverified prompt loops in production.",
            "category": "ARCHITECTURE",
        }
        slides = generate_standard_slides(topic, author="@TestAuthor")

        # 1. Enforce strict 4-slide contract
        self.assertEqual(len(slides), 4)
        self.assertEqual(slides[0]["type"], "hero")
        self.assertEqual(slides[1]["type"], "problem")
        self.assertEqual(slides[2]["type"], "solution")
        self.assertIn("code", slides[2])
        self.assertEqual(slides[3]["type"], "checklist_cta")

        # 2. Strict Zero Headline Duplication Guarantee
        self.assertEqual(slides[0]["title"], "Deterministic Agent Architectures")
        self.assertNotIn(topic["headline"], slides[1]["body"])
        self.assertNotIn(topic["headline"], slides[2]["body"])
        self.assertNotIn(topic["headline"], slides[3]["body"])

        # 3. HTML compilation checks
        html_out = build_carousel_html(slides, title="Test 4-Slide", author="@TestAuthor")
        self.assertIn("code-panel", html_out)
        self.assertIn("checklist-panel", html_out)
        self.assertIn("outro-banner", html_out)
        self.assertIn("Deterministic Agent Architectures", html_out)
        self.assertIn("1 / 4", html_out)
        self.assertIn("4 / 4", html_out)
        self.assertIn("bullet-icon-svg", html_out)
        self.assertIn("check-icon-svg", html_out)
        self.assertIn("swipe-icon-svg", html_out)

    def test_parse_linkedin_payload_monolithic_string(self):
        raw_linkedin = (
            "Deterministic Agent Architectures\n\n"
            "State machines guarantee zero dual-post bugs under strain.\n\n"
            "Key Engineering Takeaways:\n"
            "▸ Atomic state transitions prevent duplicate dispatch.\n"
            "▸ CDP socket eliminates 3rd party SaaS billing.\n"
            "▸ Polymorphic repurposing from single topic.\n\n"
            "Bottom line: Build sovereign infrastructure before scaling agents.\n\n"
            "Swipe through the architecture carousel below for the complete breakdown ➔"
        )
        parsed = parse_linkedin_payload(raw_linkedin)

        self.assertEqual(parsed["headline"], "Deterministic Agent Architectures")
        self.assertEqual(parsed["problem_context"], "State machines guarantee zero dual-post bugs under strain.")
        self.assertEqual(len(parsed["points"]), 3)
        self.assertEqual(parsed["points"][0], "Atomic state transitions prevent duplicate dispatch.")
        self.assertNotIn("▸", parsed["points"][0])
        self.assertEqual(parsed["takeaway"], "Build sovereign infrastructure before scaling agents.")
        self.assertNotIn("Bottom line:", parsed["takeaway"])
        self.assertNotIn("Swipe through", parsed["takeaway"])

        # Verify passing this raw string into generate_standard_slides produces 4 clean slides
        slides = generate_standard_slides(raw_linkedin, author="@Lordporus")
        self.assertEqual(len(slides), 4)
        self.assertNotIn("Deterministic Agent Architectures", slides[1]["body"])
        self.assertNotIn("Key Engineering Takeaways:", slides[1]["body"])
        self.assertNotIn("Swipe through", slides[3]["body"])

    def test_parse_linkedin_payload_dict_input(self):
        topic_dict = {
            "headline": "Sovereign Multi-Platform Engine",
            "body": "Unbounded API failures cause cascading desynchronization.",
            "points": ["▸ Fast-fail circuit breakers", "▸ Local vector PDF rendering"],
            "takeaway": "Reliability is an architecture, not a feature.",
            "category": "INFRASTRUCTURE",
        }
        parsed = parse_linkedin_payload(topic_dict)
        self.assertEqual(parsed["headline"], "Sovereign Multi-Platform Engine")
        self.assertEqual(parsed["problem_context"], "Unbounded API failures cause cascading desynchronization.")
        self.assertEqual(parsed["points"][0], "Fast-fail circuit breakers")
        self.assertEqual(parsed["category"], "INFRASTRUCTURE")


if __name__ == "__main__":
    unittest.main()
