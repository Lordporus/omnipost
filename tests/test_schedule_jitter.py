#!/usr/bin/env python
"""Unit and integration tests for deterministic schedule jitter and optional skipped slots."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import due
import settings
import gate


class TestScheduleJitter(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.drafts_dir = Path(self.tmp_dir) / "drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.patch_plans = patch.object(due, "PLANS", self.drafts_dir)
        self.patch_plans.start()

    def tearDown(self):
        self.patch_plans.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_compute_slot_jitter_deterministic_and_bounds(self):
        """Test compute_slot_jitter is deterministic and falls in [-15, -7] U [7, 15]."""
        self.assertTrue(hasattr(due, "compute_slot_jitter"), "due module must export compute_slot_jitter")
        
        j1 = due.compute_slot_jitter("2026-11-01", "13:00", min_minutes=7, max_minutes=15)
        j2 = due.compute_slot_jitter("2026-11-01", "13:00", min_minutes=7, max_minutes=15)
        self.assertEqual(j1, j2, "compute_slot_jitter must be 100% deterministic")

        # Check bounds: magnitude between 7 and 15
        self.assertTrue(7 <= abs(j1) <= 15, f"Jitter magnitude {abs(j1)} must be between 7 and 15")

        # Check across multiple slots and dates
        samples = [
            due.compute_slot_jitter(f"2026-11-0{d}", f"{h:02d}:00", min_minutes=7, max_minutes=15)
            for d in range(1, 10)
            for h in [13, 16, 20]
        ]
        for s in samples:
            self.assertTrue(7 <= abs(s) <= 15, f"Sample {s} out of bounds")
        # Ensure variance (not all positive or identical)
        self.assertTrue(any(s > 0 for s in samples))
        self.assertTrue(any(s < 0 for s in samples))

    def test_make_plan_deterministic_per_date(self):
        """Calling make_plan twice on the same date produces identical due_at timestamps."""
        plan1 = due.make_plan("2026-11-05")
        plan2 = due.make_plan("2026-11-05")

        self.assertEqual(len(plan1["slots"]), len(plan2["slots"]))
        for s1, s2 in zip(plan1["slots"], plan2["slots"]):
            self.assertEqual(s1["slot"], s2["slot"])
            self.assertEqual(s1["due_at"], s2["due_at"], "due_at must match deterministically across runs")
            self.assertEqual(s1.get("skipped"), s2.get("skipped"))

    def test_make_plan_applies_jitter(self):
        """make_plan applies ±7-15 min jitter to anchors instead of fixed :00."""
        plan = due.make_plan("2026-11-05")
        for s in plan["slots"]:
            due_at = datetime.fromisoformat(s["due_at"])
            anchor_h, anchor_m = (int(x) for x in s["slot"].split(":"))
            # The minute should not be anchor_m (0)
            self.assertNotEqual(due_at.minute, anchor_m, f"Slot {s['slot']} should have jitter applied")

    def test_optional_skipped_slot_preserves_ai_update(self):
        """When allow_skip is enabled, ai_update_slot is never skipped."""
        # Test across 10 dates to catch skipped slots
        skipped_count = 0
        for d in range(1, 15):
            date_str = f"2026-11-{d:02d}"
            plan = due.make_plan(date_str, allow_skip=True)
            for s in plan["slots"]:
                if s.get("skipped"):
                    skipped_count += 1
                    # Must never be ai_update
                    self.assertNotEqual(s.get("kind"), "ai_update", "ai_update slot must NEVER be skipped")
        # With 25% chance across 14 days, there should be at least one skipped slot
        self.assertGreater(skipped_count, 0, "Optional skipped slot should trigger across sample dates")

    def test_cron_gate_respects_skipped_slot(self):
        """due() skips slots marked with 'skipped', and gate emits IDLE."""
        today = datetime.now().strftime("%Y-%m-%d")
        plan = {
            "date": today,
            "created_at": datetime.now().isoformat(),
            "handle": "test_operator",
            "slots": [
                {
                    "slot": "13:00",
                    "kind": "value",
                    "due_at": (datetime.now() - timedelta(minutes=5)).isoformat(),
                    "text": "Valuable post content",
                    "image": None,
                    "posted": False,
                    "tweet_url": None,
                    "skipped": "deterministic_schedule_skip",
                }
            ],
        }
        (self.drafts_dir / f"{today}.json").write_text(json.dumps(plan), encoding="utf-8")

        # due() must return None because slot is skipped
        due_item = due.due()
        self.assertIsNone(due_item, "due() must skip slots marked with 'skipped'")


if __name__ == "__main__":
    unittest.main()
