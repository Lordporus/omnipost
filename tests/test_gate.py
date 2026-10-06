"""Unit tests for scripts/gate.py zero-cost idle schedule gate."""
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.gate import check_gate


class TestScheduleGate(unittest.TestCase):
    """Test suite for the zero-cost schedule gate stdout contract."""

    @patch("scripts.gate.due.due")
    def test_gate_idle_outputs_byte_identical_idle(self, mock_due):
        """When nothing is due, gate must emit byte-identical 'IDLE\\n' with exit code 0."""
        mock_due.return_value = None

        captured_out = io.StringIO()
        with patch("sys.stdout", captured_out):
            ret = check_gate(wake=False)

        self.assertEqual(ret, 0)
        # Exact byte-identical match
        self.assertEqual(captured_out.getvalue(), "IDLE\n")

    @patch("scripts.gate.due.tick", return_value=42)
    @patch("scripts.gate.due.due")
    def test_gate_due_outputs_json(self, mock_due, mock_tick):
        """When a post is due, gate outputs compact JSON with tick counter and exit code 0."""
        mock_due.return_value = {
            "date": "2026-10-06",
            "slot": "13:00",
            "kind": "value",
            "due_at": "2026-10-06T13:05:00+00:00",
            "text": "Automated pipeline update text.",
            "minutes_late": 10.5,
        }

        captured_out = io.StringIO()
        with patch("sys.stdout", captured_out):
            ret = check_gate(wake=False)

        self.assertEqual(ret, 0)
        out_str = captured_out.getvalue().strip()
        self.assertNotEqual(out_str, "IDLE")

        parsed = json.loads(out_str)
        self.assertEqual(parsed.get("slot"), "13:00")
        self.assertEqual(parsed.get("tick"), 42)
        self.assertEqual(parsed.get("text"), "Automated pipeline update text.")

    @patch("scripts.gate.due.tick", return_value=43)
    @patch("scripts.gate.due.due")
    def test_gate_wake_formatting(self, mock_due, mock_tick):
        """When --wake is used, outputs formatted agent prompt block and caches post.txt."""
        mock_due.return_value = {
            "date": "2026-10-06",
            "slot": "16:00",
            "kind": "ai_update",
            "due_at": "2026-10-06T16:00:00+00:00",
            "text": "Daily AI update body content.",
            "minutes_late": 5.0,
            "handle": "testoperator",
        }

        captured_out = io.StringIO()
        with patch("sys.stdout", captured_out):
            ret = check_gate(wake=True)

        self.assertEqual(ret, 0)
        out_str = captured_out.getvalue()
        self.assertIn("A post is DUE for @testoperator.", out_str)
        self.assertIn("Daily AI update body content.", out_str)
        self.assertIn("slot       16:00", out_str)

        # Check scratch post.txt written
        scratch_post = Path("scratch") / "post.txt"
        self.assertTrue(scratch_post.exists())
        self.assertEqual(scratch_post.read_text(encoding="utf-8"), "Daily AI update body content.")

    @patch("scripts.gate.due.due", side_effect=RuntimeError("Corrupt plan JSON"))
    def test_gate_error_exits_1(self, mock_due):
        """When an exception occurs, gate prints to stderr and returns code 1."""
        captured_err = io.StringIO()
        with patch("sys.stderr", captured_err):
            ret = check_gate(wake=False)

        self.assertEqual(ret, 1)
        self.assertIn("gate error", captured_err.getvalue())


if __name__ == "__main__":
    unittest.main()
