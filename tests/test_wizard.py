"""Tests for scripts/wizard.py onboarding wizard and setup.py entrypoint."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.wizard import (
    detect_system_timezone,
    main as wizard_main,
    run_wizard,
)


class TestWizard(unittest.TestCase):
    """Test suite for the interactive onboarding wizard and CI fallback."""

    def setUp(self):
        self.tmp_dir = Path("scratch") / "test_wizard_tmp"
        if self.tmp_dir.exists():
            import shutil
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        # Isolate environment from CI/host platform keys so wizard tests are hermetic
        self.env_patcher = patch.dict(os.environ, {}, clear=False)
        self.env_patcher.start()
        for k in (
            "BSKY_IDENTIFIER",
            "BSKY_APP_PASSWORD",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "DISCORD_WEBHOOK_URL",
        ):
            os.environ.pop(k, None)

    def tearDown(self):
        if hasattr(self, "env_patcher"):
            self.env_patcher.stop()
        if self.tmp_dir.exists():
            import shutil
            shutil.rmtree(self.tmp_dir)

    def test_wizard_non_interactive_creates_files(self):
        """Tests running with --non-interactive creates valid config.json and .env

        without blocking on input, and calls prereq_check.guarantee_state_files.
        """
        with patch.dict(os.environ, {
            "X_HANDLE": "ci_bot",
            "DRY_RUN": "true",
        }, clear=False):
            config, env_vars = run_wizard(
                non_interactive=True,
                test_mode=True,
                root=self.tmp_dir,
            )

        config_file = self.tmp_dir / "config.json"
        env_file = self.tmp_dir / ".env"
        state_file = self.tmp_dir / "state.json"

        self.assertTrue(config_file.exists(), "config.json should be created")
        self.assertTrue(env_file.exists(), ".env should be created")
        self.assertTrue(state_file.exists(), "state.json should be created via guarantee_state_files")

        # Verify parsed JSON structure
        saved_cfg = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertIn("platforms", saved_cfg)
        self.assertIn("timezone", saved_cfg)
        self.assertIn("slots", saved_cfg)
        self.assertEqual(saved_cfg.get("handle"), "ci_bot")
        self.assertEqual(saved_cfg.get("platforms", {}).get("x", {}).get("handle"), "ci_bot")
        self.assertTrue(saved_cfg.get("dry_run", True))

    def test_wizard_interactive_simulation(self):
        """Simulates mock input responses across all 6 wizard steps:

        1. Platform credentials (X, Bluesky, LinkedIn, Threads)
        2. Multi-LLM provider selection & key
        3. Preferences (niche topics, tone style, posting slots)
        4. Timezone selection
        5. Notification webhooks (Telegram or Discord)
        6. Operating mode (dry-run mode)
        """
        mock_inputs = [
            # Step 1: Platforms
            "alice_dev",                      # X handle
            "alice.bsky.social",              # Bluesky identifier
            "bsky-app-password-secret",       # Bluesky app password
            "https://linkedin.com/in/alice",  # LinkedIn profile URL
            "alice_threads",                  # Threads handle
            # Step 2: Multi-LLM Provider
            "gemini",                         # LLM Provider
            "gemini-test-api-key-12345",      # Gemini API key
            "gemini-2.5-flash",               # Model ID
            # Step 3: Content Preferences
            "AI agents, AI coding, dev tools",# Niche topics / queries
            "sharp and analytical",           # Voice tone
            "09:00, 13:00, 18:00, 22:00",     # Slots
            # Step 4: Timezone
            "America/New_York",               # Timezone override
            # Step 5: Webhooks
            "discord",                        # Webhook choice
            "https://discord.com/api/webhooks/test/123", # Discord webhook URL
            # Step 6: Dry Run
            "y",                              # Dry-run mode: True
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=True,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        config_file = self.tmp_dir / "config.json"
        env_file = self.tmp_dir / ".env"

        self.assertTrue(config_file.exists())
        self.assertTrue(env_file.exists())

        saved_cfg = json.loads(config_file.read_text(encoding="utf-8"))
        saved_env = env_file.read_text(encoding="utf-8")

        # Step 1 Assertions
        self.assertEqual(saved_cfg.get("handle"), "alice_dev")
        self.assertEqual(saved_cfg["platforms"]["x"]["handle"], "alice_dev")
        self.assertTrue(saved_cfg["platforms"]["x"]["enabled"])
        self.assertEqual(saved_cfg["platforms"]["bluesky"]["identifier"], "alice.bsky.social")
        self.assertTrue(saved_cfg["platforms"]["bluesky"]["enabled"])
        self.assertEqual(saved_cfg["platforms"]["linkedin"]["profile_url"], "https://linkedin.com/in/alice")
        self.assertTrue(saved_cfg["platforms"]["linkedin"]["enabled"])
        self.assertEqual(saved_cfg["platforms"]["threads"]["handle"], "alice_threads")
        self.assertTrue(saved_cfg["platforms"]["threads"]["enabled"])
        self.assertIn("BSKY_APP_PASSWORD=bsky-app-password-secret", saved_env)

        # Step 2 Assertions
        self.assertEqual(saved_cfg.get("llm", {}).get("provider"), "gemini")
        self.assertEqual(saved_cfg.get("llm", {}).get("model"), "gemini-2.5-flash")
        self.assertIn("GEMINI_API_KEY=gemini-test-api-key-12345", saved_env)
        self.assertIn("GEMINI_MODEL=gemini-2.5-flash", saved_env)

        # Step 3 Assertions
        self.assertEqual(saved_cfg.get("x_queries"), ["AI agents", "AI coding", "dev tools"])
        self.assertEqual(saved_cfg.get("voice_tone"), "sharp and analytical")
        self.assertEqual(saved_cfg.get("slots"), ["09:00", "13:00", "18:00", "22:00"])

        # Step 4 Assertions
        self.assertEqual(saved_cfg.get("timezone"), "America/New_York")

        # Step 5 Assertions
        self.assertTrue(saved_cfg.get("notifications", {}).get("discord", {}).get("enabled"))
        self.assertIn("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/test/123", saved_env)

        # Step 6 Assertions
        self.assertTrue(saved_cfg.get("dry_run"))

    def test_wizard_timezone_detection(self):
        """Verifies auto-detection of timezone with fallback."""
        tz = detect_system_timezone()
        self.assertIsInstance(tz, str)
        self.assertTrue(len(tz) > 0)

        # Test fallback when exception occurs
        with patch("scripts.wizard._resolve_system_timezone", side_effect=Exception("Detection error")):
            fallback_tz = detect_system_timezone()
            self.assertEqual(fallback_tz, "local")

    def test_wizard_dry_run_flag(self):
        """Tests dry_run configuration output when user enters 'n' vs 'y'."""
        # Case 1: user opts out of dry-run ('n')
        inputs_no = [
            "", "", "", "",     # Platforms skipped
            "local",            # Provider
            "", "", "",         # Preferences default
            "",                 # Timezone default
            "none",             # Webhooks none
            "n",                # Dry run false
        ]
        config_no, _ = run_wizard(
            non_interactive=False,
            test_mode=True,
            root=self.tmp_dir,
            inputs=inputs_no,
        )
        self.assertFalse(config_no.get("dry_run"))

        # Case 2: user accepts dry-run ('y')
        inputs_yes = [
            "", "", "", "",     # Platforms skipped
            "local",            # Provider
            "", "", "",         # Preferences default
            "",                 # Timezone default
            "none",             # Webhooks none
            "y",                # Dry run true
        ]
        config_yes, _ = run_wizard(
            non_interactive=False,
            test_mode=True,
            root=self.tmp_dir,
            inputs=inputs_yes,
        )
        self.assertTrue(config_yes.get("dry_run"))

    def test_wizard_state_files_guaranteed(self):
        """Verifies state.json and .env exist on disk after wizard completes."""
        run_wizard(
            non_interactive=True,
            test_mode=True,
            root=self.tmp_dir,
        )

        state_path = self.tmp_dir / "state.json"
        env_path = self.tmp_dir / ".env"

        self.assertTrue(state_path.exists())
        self.assertTrue(state_path.is_file())
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8")), {})

        self.assertTrue(env_path.exists())
        self.assertTrue(env_path.is_file())

    def test_wizard_telegram_webhooks(self):
        """Tests telegram webhook selection and environment variable generation."""
        mock_inputs = [
            "", "", "", "",     # Platforms skipped
            "local",            # Provider
            "", "", "",         # Preferences
            "",                 # Timezone
            "telegram",         # Webhook choice
            "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", # Bot token
            "987654321",        # Chat ID
            "y",                # Dry run
        ]
        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=True,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )
        self.assertTrue(config.get("notifications", {}).get("telegram", {}).get("enabled"))
        self.assertEqual(env_vars.get("TELEGRAM_BOT_TOKEN"), "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        self.assertEqual(env_vars.get("TELEGRAM_CHAT_ID"), "987654321")

    @patch("scripts.wizard.validate_bluesky_credentials")
    @patch("scripts.wizard.validate_llm_key")
    @patch("scripts.wizard.validate_model_id")
    @patch("scripts.wizard.validate_webhook")
    def test_wizard_live_validation_called(self, mock_val_wh, mock_val_model, mock_val_llm, mock_val_bsky):
        """Verifies validator routines are executed when test_mode=False."""
        mock_val_bsky.return_value = (True, "Verified")
        mock_val_llm.return_value = (True, "Verified")
        mock_val_model.return_value = (True, "Verified")
        mock_val_wh.return_value = (True, "Verified")

        mock_inputs = [
            "",                                  # X handle
            "bob.bsky.social",                   # Bluesky identifier
            "bsky-pass-123",                     # Bluesky password
            "",                                  # LinkedIn
            "",                                  # Threads
            "openai",                            # Provider
            "sk-openai-key-test",                # API key
            "gpt-4o-mini",                       # Model ID
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "discord",                           # Webhook choice
            "https://discord.com/api/webhooks/1",# Discord URL
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        mock_val_bsky.assert_called_once_with("bob.bsky.social", "bsky-pass-123")
        mock_val_llm.assert_called_once_with("openai", "sk-openai-key-test")
        mock_val_model.assert_called_once_with("openai", "sk-openai-key-test", "gpt-4o-mini")
        mock_val_wh.assert_called_once_with("discord", "https://discord.com/api/webhooks/1")

    def test_wizard_defaults_flag(self):
        """Tests that defaults=True runs unattended without input iteration."""
        config, env_vars = run_wizard(
            defaults=True,
            test_mode=True,
            root=self.tmp_dir,
        )
        self.assertIn("platforms", config)
        self.assertIn("timezone", config)
        self.assertTrue(config.get("dry_run"))

    @patch("scripts.wizard.validate_bluesky_credentials")
    def test_wizard_bluesky_validation_failure_decline_disables_channel(self, mock_val_bsky):
        """When Bluesky credential validation fails and operator declines retry, channel is disabled."""
        mock_val_bsky.return_value = (False, "Invalid identifier or password")

        mock_inputs = [
            "",                                  # X handle (skip)
            "bob.bsky.social",                   # Bluesky handle
            "wrong-password",                    # Bluesky app password
            "n",                                 # Re-enter credentials? [y/N]: n
            "",                                  # LinkedIn (skip)
            "",                                  # Threads (skip)
            "local",                             # Provider
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertFalse(config["platforms"]["bluesky"]["enabled"])
        self.assertEqual(config["platforms"]["bluesky"]["identifier"], "bob.bsky.social")
        self.assertNotIn("BSKY_APP_PASSWORD", env_vars)

    @patch("scripts.wizard.validate_bluesky_credentials")
    def test_wizard_bluesky_validation_retry_success(self, mock_val_bsky):
        """When Bluesky credentials fail on first attempt, operator can retry and succeed."""
        mock_val_bsky.side_effect = [(False, "Invalid password"), (True, "OK")]

        mock_inputs = [
            "",                                  # X handle (skip)
            "bob.bsky.social",                   # Bluesky handle
            "wrong-password",                    # 1st attempt: wrong password
            "y",                                 # Re-enter credentials? [y/N]: y
            "bob.bsky.social",                   # Bluesky handle confirmation
            "correct-password",                  # 2nd attempt: correct password
            "",                                  # LinkedIn (skip)
            "",                                  # Threads (skip)
            "local",                             # Provider
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertTrue(config["platforms"]["bluesky"]["enabled"])
        self.assertEqual(env_vars.get("BSKY_APP_PASSWORD"), "correct-password")
        self.assertEqual(mock_val_bsky.call_count, 2)

    @patch("scripts.wizard.validate_llm_key")
    def test_wizard_llm_validation_failure_decline_falls_back_to_local(self, mock_val_llm):
        """When LLM API key validation fails and operator declines retry, provider falls back to local."""
        mock_val_llm.return_value = (False, "API key unauthorized")

        mock_inputs = [
            "", "", "", "",                      # Platforms skipped
            "openai",                            # Provider
            "bad-api-key",                       # API Key
            "n",                                 # Re-enter credentials? [y/N]: n
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertEqual(config["llm"]["provider"], "local")
        self.assertNotIn("OPENAI_API_KEY", env_vars)

    @patch("scripts.wizard.validate_model_id")
    @patch("scripts.wizard.validate_llm_key")
    def test_wizard_llm_validation_retry_success(self, mock_val_llm, mock_val_model):
        """When LLM API key fails on first attempt, operator can retry and succeed."""
        mock_val_llm.side_effect = [(False, "Invalid key"), (True, "OK")]
        mock_val_model.return_value = (True, "Verified")

        mock_inputs = [
            "", "", "", "",                      # Platforms skipped
            "openai",                            # Provider
            "bad-api-key",                       # 1st attempt
            "y",                                 # Re-enter credentials? [y/N]: y
            "good-api-key",                      # 2nd attempt
            "gpt-4o-mini",                       # Model ID
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertEqual(config["llm"]["provider"], "openai")
        self.assertEqual(config["llm"]["model"], "gpt-4o-mini")
        self.assertEqual(env_vars.get("OPENAI_API_KEY"), "good-api-key")
        self.assertEqual(env_vars.get("OPENAI_MODEL"), "gpt-4o-mini")
        self.assertEqual(mock_val_llm.call_count, 2)

    @patch("scripts.wizard.validate_webhook")
    def test_wizard_webhook_validation_failure_decline_disables_webhook(self, mock_val_wh):
        """When webhook validation fails and operator declines retry, notification is disabled."""
        mock_val_wh.return_value = (False, "Webhook endpoint unreachable")

        mock_inputs = [
            "", "", "", "",                      # Platforms skipped
            "local",                             # Provider
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "discord",                           # Webhook choice
            "https://discord.com/bad/url",       # Webhook URL
            "n",                                 # Re-enter credentials? [y/N]: n
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertFalse(config.get("notifications", {}).get("discord", {}).get("enabled", True))
        self.assertNotIn("DISCORD_WEBHOOK_URL", env_vars)

    @patch("scripts.wizard.validate_model_id")
    @patch("scripts.wizard.validate_llm_key")
    def test_wizard_model_validation_failure_and_retry(self, mock_val_llm, mock_val_model):
        """When model validation fails on first attempt, operator can retry with valid model."""
        mock_val_llm.return_value = (True, "OK")
        mock_val_model.side_effect = [(False, "Model not found"), (True, "OK")]

        mock_inputs = [
            "", "", "", "",                      # Platforms skipped
            "gemini",                            # Provider
            "valid-gemini-key",                  # API Key
            "gemini-deprecated-99",              # 1st attempt: invalid model
            "y",                                 # Re-enter Model ID? [y/N]: y
            "gemini-2.5-flash",                  # 2nd attempt: valid model
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertEqual(config["llm"]["provider"], "gemini")
        self.assertEqual(config["llm"]["model"], "gemini-2.5-flash")
        self.assertEqual(env_vars.get("GEMINI_MODEL"), "gemini-2.5-flash")
        self.assertEqual(mock_val_model.call_count, 2)

    @patch("scripts.wizard.validate_model_id")
    @patch("scripts.wizard.validate_llm_key")
    def test_wizard_model_validation_failure_decline_retains_default(self, mock_val_llm, mock_val_model):
        """When model validation fails and operator declines retry, wizard falls back to default model."""
        mock_val_llm.return_value = (True, "OK")
        mock_val_model.return_value = (False, "Model not found")

        mock_inputs = [
            "", "", "", "",                      # Platforms skipped
            "gemini",                            # Provider
            "valid-gemini-key",                  # API Key
            "gemini-deprecated-99",              # Invalid model
            "n",                                 # Re-enter Model ID? [y/N]: n (retains default)
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=False,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertEqual(config["llm"]["provider"], "gemini")
        self.assertEqual(config["llm"]["model"], "gemini-2.5-flash")
        self.assertEqual(env_vars.get("GEMINI_MODEL"), "gemini-2.5-flash")

    def test_wizard_provider_numbered_shortcuts(self):
        """Entering '1' selects gemini, '2' selects openai, etc."""
        mock_inputs = [
            "", "", "", "",                      # Platforms skipped
            "1",                                 # Provider shortcut for 'gemini'
            "test-gemini-key",                   # API Key
            "gemini-2.5-flash",                  # Model ID
            "", "", "",                          # Preferences
            "",                                  # Timezone
            "none",                              # Webhook
            "y",                                 # Dry run
        ]

        config, env_vars = run_wizard(
            non_interactive=False,
            test_mode=True,
            root=self.tmp_dir,
            inputs=mock_inputs,
        )

        self.assertEqual(config["llm"]["provider"], "gemini")
        self.assertEqual(config["llm"]["model"], "gemini-2.5-flash")

    def test_validator_model_id_probe(self):
        """Unit tests for validate_model_id in scripts/validator.py."""
        from scripts.validator import validate_model_id

        # Empty inputs
        ok, msg = validate_model_id("gemini", "", "gemini-2.5-flash")
        self.assertFalse(ok)
        self.assertIn("API key cannot be empty", msg)

        ok, msg = validate_model_id("gemini", "key", "")
        self.assertFalse(ok)
        self.assertIn("Model ID cannot be empty", msg)

        # Illegal regex characters (SSRF prevention)
        ok, msg = validate_model_id("gemini", "key", "../../malicious;cmd")
        self.assertFalse(ok)
        self.assertIn("illegal characters", msg)

        # Mocked successful probe
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"name": "models/gemini-2.5-flash"}'
            mock_url.return_value.__enter__.return_value = mock_resp

            ok, msg = validate_model_id("gemini", "valid-key", "gemini-2.5-flash")
            self.assertTrue(ok)
            self.assertIn("verified successfully", msg)


class TestSetupEntrypoint(unittest.TestCase):
    """Test suite for setup.py entrypoint invoking wizard."""

    def test_setup_entrypoint_execution(self):
        root = Path(__file__).resolve().parent.parent
        setup_script = root / "setup.py"
        self.assertTrue(setup_script.exists(), "setup.py must exist at repo root")

        # Invoke setup.py with --non-interactive and --test-mode pointing to a scratch root
        tmp_root = root / "scratch" / "test_setup_entrypoint_tmp"
        if tmp_root.exists():
            import shutil
            shutil.rmtree(tmp_root)
        tmp_root.mkdir(parents=True, exist_ok=True)

        try:
            res = subprocess.run(
                [
                    sys.executable,
                    str(setup_script),
                    "--non-interactive",
                    "--test-mode",
                    "--root",
                    str(tmp_root),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"setup.py failed with: {res.stderr}")
            self.assertTrue((tmp_root / "config.json").exists())
            self.assertTrue((tmp_root / ".env").exists())
            self.assertTrue((tmp_root / "state.json").exists())
        finally:
            if tmp_root.exists():
                import shutil
                shutil.rmtree(tmp_root)


if __name__ == "__main__":
    unittest.main()
