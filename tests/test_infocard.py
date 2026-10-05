"""Unit tests for the render.infocard programmatic generator."""
import unittest
from pathlib import Path
from PIL import Image

from render.infocard import create_infocard, WIDTH, HEIGHT


class TestInfocardRenderer(unittest.TestCase):
    """Test suite for programmatic dark-mode infocard creation."""

    def setUp(self):
        self.output_dir = Path("scratch/test_renders")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.output_dir / "sample_card.png"

    def tearDown(self):
        if self.output_file.exists():
            self.output_file.unlink()

    def test_infocard_generation_and_dimensions(self):
        path = create_infocard(
            title="Building Autonomous Agents with Pure Python",
            body="CDP automation bypasses $200/mo API paywalls cleanly.\nNative ATProto handles Bluesky over HTTP.",
            tag="ARCHITECTURE",
            author="@Lordporus • OmniPost",
            output_path=self.output_file,
        )

        self.assertTrue(path.exists())
        self.assertEqual(path, self.output_file)

        # Inspect generated image properties
        with Image.open(path) as img:
            self.assertEqual(img.format, "PNG")
            self.assertEqual(img.size, (WIDTH, HEIGHT))
            self.assertEqual(img.size, (1200, 675))

    def test_infocard_long_text_wrapping(self):
        long_title = "This is an extremely long headline that will definitely wrap across multiple lines in our test rendering without crashing or raising any layout exceptions"
        long_body = (
            "Paragraph 1 contains lots of detailed technical text discussing software architecture.\n"
            "Paragraph 2 continues with bullet points:\n"
            "• Point Alpha: Deterministic state machines enforce predictable workflows\n"
            "• Point Beta: Browser CDP automation interacts directly with active DOM sessions\n"
            "• Point Gamma: Rich text facets require exact UTF-8 byte slice calculations"
        )
        path = create_infocard(
            title=long_title,
            body=long_body,
            tag="AI DEEP DIVE",
            output_path=self.output_file,
        )

        self.assertTrue(path.exists())
        with Image.open(path) as img:
            self.assertEqual(img.size, (1200, 675))

    def test_default_output_path(self):
        default_path = create_infocard(
            title="Default Path Test",
            body="Ensures default path creation works when output_path is None.",
        )
        self.assertTrue(default_path.exists())
        self.assertIn("infocards", str(default_path))


if __name__ == "__main__":
    unittest.main()
