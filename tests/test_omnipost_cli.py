#!/usr/bin/env python
"""Unit test suite for OmniPost standalone CLI entrypoints.

Tests:
1. Root entrypoint omnipost.py (--help and dispatch)
2. Module entrypoint omnipost/__main__.py (-m omnipost)
3. Parser configuration and subcommand structure
4. Command dispatch for doctor, browser, plan, post/drop
5. Error handling and unknown command handling
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from omnipost.cli import build_parser, main as cli_main


class TestOmniPostCLIParser(unittest.TestCase):
    """Test argument parser definitions and options."""

    def setUp(self):
        self.parser = build_parser()

    def test_parser_has_expected_subcommands(self):
        subparsers_action = [
            action for action in self.parser._actions
            if action.dest == "command"
        ][0]
        commands = set(subparsers_action.choices.keys())
        expected = {"post", "drop", "doctor", "setup", "browser", "plan", "daemon"}
        self.assertTrue(expected.issubset(commands), f"Missing commands: {expected - commands}")

    def test_post_subcommand_arguments(self):
        args = self.parser.parse_args(["post", "--dry-run", "--platforms", "x,bluesky", "--archetype", "framework"])
        self.assertEqual(args.command, "post")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.platforms, "x,bluesky")
        self.assertEqual(args.archetype, "framework")

    def test_drop_alias_shares_post_options(self):
        args = self.parser.parse_args(["drop", "--topic", "Agentic Systems", "--dry-run"])
        self.assertEqual(args.command, "drop")
        self.assertEqual(args.topic, "Agentic Systems")
        self.assertTrue(args.dry_run)

    def test_doctor_subcommand_arguments(self):
        args = self.parser.parse_args(["doctor", "--no-live", "--json"])
        self.assertEqual(args.command, "doctor")
        self.assertFalse(args.live)
        self.assertTrue(args.json)

    def test_browser_subcommand_actions(self):
        for action in ("info", "status", "start", "stop"):
            args = self.parser.parse_args(["browser", action])
            self.assertEqual(args.command, "browser")
            self.assertEqual(args.action, action)

    def test_plan_subcommand_arguments(self):
        args = self.parser.parse_args(["plan", "--make-plan"])
        self.assertEqual(args.command, "plan")
        self.assertTrue(args.make)


class TestOmniPostCLIDispatch(unittest.TestCase):
    """Test internal command handlers dispatch correctly."""

    @patch("scripts.doctor.main", return_value=0)
    def test_dispatch_doctor(self, mock_doctor):
        exit_code = cli_main(["doctor", "--no-live"])
        self.assertEqual(exit_code, 0)
        mock_doctor.assert_called_once()
        call_args = mock_doctor.call_args[0][0]
        self.assertNotIn("--live", call_args)

    @patch("scripts.due.main", return_value=0)
    def test_dispatch_plan_make_plan(self, mock_due):
        exit_code = cli_main(["plan", "--make-plan"])
        self.assertEqual(exit_code, 0)
        mock_due.assert_called_once_with(["make-plan"])

    @patch("scripts.publish_now.main_with_args", return_value=0)
    def test_dispatch_post_direct_text(self, mock_pub):
        exit_code = cli_main(["post", "--text", "Test post content", "--dry-run", "--platforms", "x"])
        self.assertEqual(exit_code, 0)
        mock_pub.assert_called_once()
        kwargs = mock_pub.call_args[1]
        self.assertTrue(kwargs.get("dry_run"))
        self.assertEqual(kwargs.get("platforms"), "x")
        self.assertEqual(kwargs.get("text"), "Test post content")

    def test_dispatch_no_args_shows_help(self):
        exit_code = cli_main([])
        self.assertEqual(exit_code, 0)

    def test_dispatch_analytics_and_radar(self):
        with patch("scripts.profile_audit.run_analytics", return_value=0) as mock_an:
            self.assertEqual(cli_main(["analytics", "--no-sync"]), 0)
            mock_an.assert_called_once_with(sync_samples=False)

        with patch("scripts.profile_audit.run_radar", return_value=0) as mock_rad:
            self.assertEqual(cli_main(["radar", "--limit", "3"]), 0)
            mock_rad.assert_called_once_with(limit=3)


class TestOmniPostCLIExecutable(unittest.TestCase):
    """Test running omnipost CLI entrypoints as standalone processes."""

    def test_omnipost_py_help(self):
        script = ROOT / "omnipost.py"
        res = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Autonomous Multi-Platform Thought Leadership Engine", res.stdout)
        self.assertIn("doctor", res.stdout)
        self.assertIn("post", res.stdout)

    def test_module_execution_help(self):
        res = subprocess.run(
            [sys.executable, "-m", "omnipost", "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Autonomous Multi-Platform Thought Leadership Engine", res.stdout)


if __name__ == "__main__":
    unittest.main()
