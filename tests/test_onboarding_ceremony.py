"""Unit tests for voice profile ritual, DO-NOT enforcement, and onboarding ceremony."""
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.voice_profile import (
    validate_voice_profile_exists,
    enforce_do_not_list,
    generate_voice_profile_markdown,
    run_voice_ritual,
)
from scripts.wizard import run_wizard


class TestOnboardingCeremony(unittest.TestCase):
    """Test suite for voice authenticity measurement ritual and wizard ceremonies."""

    def setUp(self):
        self.tmp_dir = Path("scratch") / "test_ceremony_tmp"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_run_voice_ritual_success(self):
        sample_posts = [
            "We built a direct CDP adapter without Selenium.\n\nLatency dropped from 450ms to 42ms. Zero browser bloat.",
            "PostgreSQL index bloat solved with REINDEX CONCURRENTLY.\n\n3 key queries went from 120ms to 4ms in production.",
            "SQLite WAL mode gives 4x write throughput under concurrent readers.\n\nAlways set busy_timeout=5000.",
            "Why Python stdlib urllib beats requests for micro-CLIs:\n\nZero dependencies, instant startup time.",
        ]

        analysis, out_file = run_voice_ritual(sample_posts, base=self.tmp_dir, handle="testuser")
        self.assertTrue(out_file.exists())
        self.assertGreater(analysis["posts_analysed"], 3)


        content = out_file.read_text(encoding="utf-8")
        self.assertIn("# Voice Profile: @testuser", content)
        self.assertIn("## DO NOT LIST", content)
        self.assertIn("Never use corporate buzzwords", content)

        # Verify exists helper
        self.assertTrue(validate_voice_profile_exists(base=self.tmp_dir))

        # Verify do-not list enforcement helper
        ok, rules = enforce_do_not_list(profile_text=content)
        self.assertTrue(ok)
        self.assertGreaterEqual(len(rules), 5)

    def test_run_voice_ritual_rejects_under_3_posts(self):
        too_few = [
            "Single isolated post about Python async."
        ]
        with self.assertRaises(ValueError) as ctx:
            run_voice_ritual(too_few, base=self.tmp_dir)
        self.assertIn("requires at least 3 sample posts", str(ctx.exception))

    def test_enforce_do_not_list_missing_section(self):
        malformed_profile = """# Voice Profile: @someone
## Quantitative Habits
- Median length: 150 chars
## Hook Patterns
1. "Testing"
"""
        ok, rules = enforce_do_not_list(profile_text=malformed_profile)
        self.assertFalse(ok)
        self.assertEqual(rules, [])

    def test_validate_voice_profile_exists_missing_or_empty(self):
        empty_dir = self.tmp_dir / "empty"
        empty_dir.mkdir(parents=True, exist_ok=True)
        self.assertFalse(validate_voice_profile_exists(base=empty_dir))

        ref_dir = empty_dir / "references"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "voice-profile.local.md").write_text("tiny", encoding="utf-8")
        self.assertFalse(validate_voice_profile_exists(base=empty_dir))

    def test_wizard_ceremony_integrates_cleanly(self):
        """Verify run_wizard executes smoothly with new ceremony hooks in non_interactive test mode."""
        cfg, env_vars = run_wizard(
            non_interactive=True,
            test_mode=True,
            root=self.tmp_dir,
        )
        self.assertIn("platforms", cfg)
        self.assertTrue((self.tmp_dir / "config.json").exists())


if __name__ == "__main__":
    unittest.main()
