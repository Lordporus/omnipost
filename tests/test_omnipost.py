#!/usr/bin/env python
"""Unit test suite for OmniPost core logic.

Zero external dependencies: uses Python standard library unittest.
Tests offline pure-logic components:
- Configuration loading & defaults
- Character limit resolution and warning signals
- Timezone and schedule jitter/gap calculations
- Research parsing, HTML sanitization, and deduplication
- Voice profile statistical metrics and hook pattern classification
- Doctor environment readiness checks
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

# Ensure scripts directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import settings
import due
import research
import voice_profile
import doctor


class TestSettings(unittest.TestCase):
    def test_defaults_structure(self):
        cfg = settings.load(required=False)
        self.assertIn("timezone", cfg)
        self.assertIn("slots", cfg)
        self.assertIn("jitter_minutes", cfg)
        self.assertIn("browser", cfg)

    def test_limit_resolution(self):
        # Case 1: unconfigured / unmeasured -> fallback to ASSUMED_LIMIT (280) with warning
        res_assumed = settings.limit({"max_chars": None, "max_chars_verified": False})
        self.assertEqual(res_assumed["chars"], 280)
        self.assertFalse(res_assumed["verified"])
        self.assertIsNotNone(res_assumed["fix"])

        # Case 2: configured but not verified
        res_unverified = settings.limit({"max_chars": 500, "max_chars_verified": False})
        self.assertEqual(res_unverified["chars"], 500)
        self.assertFalse(res_unverified["verified"])

        # Case 3: configured and verified
        res_verified = settings.limit({"max_chars": 25000, "max_chars_verified": True})
        self.assertEqual(res_verified["chars"], 25000)
        self.assertTrue(res_verified["verified"])
        self.assertIsNone(res_verified["fix"])

    def test_profile_dir_fallback(self):
        prof = settings.profile_dir()
        self.assertTrue(isinstance(prof, Path))
        self.assertTrue(str(prof).endswith("chrome-profile") or "profile" in str(prof).lower())


class TestDue(unittest.TestCase):
    def test_make_plan_structure(self):
        plan = due.make_plan("2026-10-10")
        self.assertEqual(plan["date"], "2026-10-10")
        self.assertTrue(len(plan["slots"]) >= 1)
        for s in plan["slots"]:
            self.assertIn("slot", s)
            self.assertIn("kind", s)
            self.assertIn("due_at", s)
            self.assertFalse(s["posted"])

    def test_tick_increment(self):
        t1 = due.tick()
        t2 = due.tick()
        self.assertEqual(t2, t1 + 1)


class TestResearch(unittest.TestCase):
    def test_strip_html(self):
        raw = "<p>Hello <b>World</b> &amp; &quot;AI&quot; <script>alert(1)</script></p>"
        cleaned = research.strip_html(raw)
        self.assertEqual(cleaned, 'Hello World & "AI"')

    def test_dedupe(self):
        items = [
            {"title": "Open Source LLM Release", "url": "https://example.com/item1?ref=hn"},
            {"title": "Open Source LLM Release", "url": "https://example.com/item1"},
            {"title": "Different News", "url": "https://example.com/item2"},
        ]
        deduped = research.dedupe(items)
        self.assertEqual(len(deduped), 2)

    def test_rank_key(self):
        it1 = {"source": "hn", "score": 200, "comments": 50, "created": datetime.now(timezone.utc).isoformat()}
        it2 = {"source": "hn", "score": 10, "comments": 2, "created": datetime.now(timezone.utc).isoformat()}
        k1 = research.rank_key(it1)
        k2 = research.rank_key(it2)
        # Lower key tuple means higher rank (because negative score)
        self.assertLess(k1[0], k2[0])


class TestVoiceProfile(unittest.TestCase):
    def test_analyse_posts(self):
        posts = [
            "AI agents aren't replacing developers.\n\nThey're multiplying what one person can ship.\n\nBuild systems, not scripts.",
            "Solo founders in 2026 are running 4-agent pipelines:\n- Triage\n- Research\n- Testing\n\nOne operator is now an agency.",
            "Stop writing prompts without evals.\n\nIf you can't measure output quality, your prompt engineering is guessing.",
        ]
        res = voice_profile.analyse(posts)
        self.assertEqual(res["posts_analysed"], 3)
        self.assertTrue(res["length"]["median"] > 0)
        self.assertEqual(res["structure"]["beats_per_post_median"], 2)
        self.assertIn("directive / addressed to the reader", res["hook_openers"])


class TestDoctor(unittest.TestCase):
    def test_check_python(self):
        status, detail = doctor.check_python()
        self.assertEqual(status, doctor.OK)
        self.assertIn("python 3.", detail)

    def test_check_deps(self):
        status, detail = doctor.check_deps()
        self.assertEqual(status, doctor.OK)
        self.assertIn("websockets installed", detail)

    def test_check_dirs(self):
        status, detail = doctor.check_dirs()
        self.assertEqual(status, doctor.OK)


if __name__ == "__main__":
    unittest.main()
