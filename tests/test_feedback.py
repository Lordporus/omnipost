"""Unit tests for closed-loop feedback engine in scripts/feedback.py."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import feedback, ledger


class TestFeedbackEngine(unittest.TestCase):
    """Test suite for hook classification, performance analysis, and voice profile updating."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.state_file = self.temp_path / "state.json"
        self.profile_file = self.temp_path / "voice-profile.local.md"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_classify_hook_patterns(self):
        # Question hooks
        self.assertEqual(
            feedback.classify_hook("Why do 90% of autonomous agents fail in production?\n\nBecause of unconstrained loops."),
            "Question",
        )
        self.assertEqual(
            feedback.classify_hook("How can a solo engineer build an agency with AI?\nHere is the stack."),
            "Question",
        )

        # Contrarian hooks
        self.assertEqual(
            feedback.classify_hook("Most founders are wrong about agentic coding.\n\nPrompt engineering is dead."),
            "Contrarian",
        )
        self.assertEqual(
            feedback.classify_hook("Solo founders in 2026 aren't competing on hours worked.\nThey compete on leverage."),
            "Contrarian",
        )

        # Numbered breakdown
        self.assertEqual(
            feedback.classify_hook("3 lessons from deploying 50 AI agents in production:\n1. State machines"),
            "Numbered Breakdown",
        )
        self.assertEqual(
            feedback.classify_hook("5 steps to deterministic tool calling:\nFirst step is schema."),
            "Numbered Breakdown",
        )

        # Declarative insight
        self.assertEqual(
            feedback.classify_hook("Determinism is the real moat of autonomous systems in 2026."),
            "Declarative Insight",
        )

    def test_analyze_performance_extracts_best_hook(self):
        test_state = {
            "version": "2.0",
            "posts": [
                {
                    "date": "2026-10-04",
                    "slot": "13:00",
                    "text": "Most developers are wrong about AI agents.\nContrarian view.",
                    "platforms": {
                        "x": {
                            "status": "published",
                            "metrics": {"likes": 100, "reposts": 20, "replies": 10, "views": 2000},
                        }
                    },
                },
                {
                    "date": "2026-10-04",
                    "slot": "16:00",
                    "text": "Why do AI agents hallucinate in long workflows?\nQuestion hook.",
                    "platforms": {
                        "bluesky": {
                            "status": "published",
                            "metrics": {"likes": 20, "reposts": 2, "replies": 1, "views": 0},
                        }
                    },
                },
            ],
        }
        ledger.save_state(test_state, self.state_file)

        analysis = feedback.analyze_performance(self.state_file)
        self.assertEqual(analysis["total_items"], 2)
        # Contrarian had score 100 + 40 + 30 + 20 = 190, vs Question 20 + 4 + 3 = 27
        self.assertEqual(analysis["best_hook_archetype"], "Contrarian")
        self.assertIn("Contrarian", analysis["archetype_scores"])
        self.assertIn("Question", analysis["archetype_scores"])
        self.assertGreater(analysis["archetype_scores"]["Contrarian"], analysis["archetype_scores"]["Question"])

    def test_update_voice_profile_appends_and_updates_section(self):
        # Create initial profile
        initial_profile = (
            "# Voice Profile — @Lordporus\n\n"
            "## Measured Profile\n"
            "- **Target ceiling:** 280 characters.\n\n"
            "## Do-Not List\n"
            "- Never use hashtags\n"
        )
        self.profile_file.write_text(initial_profile, encoding="utf-8")

        analysis = {
            "best_hook_archetype": "Contrarian",
            "optimal_char_length": 215,
            "archetype_scores": {"Contrarian": 125.5, "Question": 42.0},
            "top_posts": [
                {
                    "text": "Most founders are wrong about AI leverage.\nFull insight...",
                    "platform": "x",
                    "score": 125.5,
                }
            ],
        }

        # First update (appends)
        updated_1 = feedback.update_voice_profile(analysis, self.profile_file)
        self.assertIn("## Learned Algorithmic Preferences", updated_1)
        self.assertIn("Top-Performing Hook Archetype:** Contrarian", updated_1)
        self.assertIn("## Do-Not List", updated_1)

        # Second update (replaces existing section without duplicating)
        analysis["best_hook_archetype"] = "Numbered Breakdown"
        updated_2 = feedback.update_voice_profile(analysis, self.profile_file)
        self.assertEqual(updated_2.count("## Learned Algorithmic Preferences"), 1)
        self.assertIn("Top-Performing Hook Archetype:** Numbered Breakdown", updated_2)
        self.assertIn("## Do-Not List", updated_2)


if __name__ == "__main__":
    unittest.main()
