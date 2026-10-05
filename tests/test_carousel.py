"""Unit tests for the render.carousel HTML builder and CDP PDF exporter."""
import base64
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from render.carousel import build_carousel_html, create_carousel_pdf


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


if __name__ == "__main__":
    unittest.main()
