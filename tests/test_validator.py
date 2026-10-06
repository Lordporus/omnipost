"""Tests for scripts/validator.py credential and webhook ping engine."""
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from scripts.validator import (
    validate_bluesky_credentials,
    validate_llm_key,
    validate_webhook,
)


class TestBlueskyValidation(unittest.TestCase):
    """Test suite for Bluesky credential validation."""

    def test_missing_credentials(self):
        ok, msg = validate_bluesky_credentials("", "")
        self.assertFalse(ok)
        self.assertIn("required", msg.lower())

        ok, msg = validate_bluesky_credentials("user.bsky.social", "")
        self.assertFalse(ok)
        self.assertIn("required", msg.lower())

    @patch("scripts.validator.urllib.request.urlopen")
    def test_success_200(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "handle": "alice.bsky.social",
            "did": "did:plc:12345",
            "accessJwt": "jwt.sample",
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_bluesky_credentials("alice.bsky.social", "app-pass-word")
        self.assertTrue(ok)
        self.assertIn("alice.bsky.social", msg)

    @patch("scripts.validator.urllib.request.urlopen")
    def test_unauthorized_401(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://bsky.social/xrpc/com.atproto.server.createSession",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message": "Invalid identifier or password"}'),
        )

        ok, msg = validate_bluesky_credentials("alice.bsky.social", "wrong-password")
        self.assertFalse(ok)
        self.assertIn("Invalid identifier or password", msg)

    @patch("scripts.validator.urllib.request.urlopen")
    def test_network_timeout_or_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

        ok, msg = validate_bluesky_credentials("alice.bsky.social", "any-password")
        self.assertFalse(ok)
        self.assertIn("Connection timed out", msg)


class TestLLMKeyValidation(unittest.TestCase):
    """Test suite for LLM provider key validation."""

    def test_local_mode_and_empty_provider(self):
        ok, msg = validate_llm_key("local", "")
        self.assertTrue(ok)
        self.assertIn("zero-cost", msg.lower())

        ok, msg = validate_llm_key("", "")
        self.assertTrue(ok)
        self.assertIn("zero-cost", msg.lower())

        ok, msg = validate_llm_key("none", "")
        self.assertTrue(ok)
        self.assertIn("zero-cost", msg.lower())

    def test_missing_key_for_remote_provider(self):
        ok, msg = validate_llm_key("openai", "")
        self.assertFalse(ok)
        self.assertIn("key is required", msg.lower())

    @patch("scripts.validator.urllib.request.urlopen")
    def test_gemini_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"models": [{"name": "gemini-1.5-pro"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_llm_key("gemini", "AIzaSyFakeGeminiKey")
        self.assertTrue(ok)
        self.assertIn("Gemini", msg)
        req = mock_urlopen.call_args[0][0]
        self.assertIn("generativelanguage.googleapis.com", req.full_url)
        self.assertIn("key=AIzaSyFakeGeminiKey", req.full_url)

    @patch("scripts.validator.urllib.request.urlopen")
    def test_openai_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"data": [{"id": "gpt-4o"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_llm_key("openai", "sk-proj-testkey")
        self.assertTrue(ok)
        self.assertIn("OpenAI", msg)
        req = mock_urlopen.call_args[0][0]
        self.assertIn("api.openai.com/v1/models", req.full_url)
        self.assertEqual(req.headers.get("Authorization"), "Bearer sk-proj-testkey")

    @patch("scripts.validator.urllib.request.urlopen")
    def test_claude_anthropic_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"data": [{"id": "claude-3-5-sonnet"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_llm_key("claude", "sk-ant-testkey")
        self.assertTrue(ok)
        self.assertIn("Claude", msg)
        req = mock_urlopen.call_args[0][0]
        self.assertIn("api.anthropic.com/v1/models", req.full_url)
        self.assertEqual(req.headers.get("X-api-key"), "sk-ant-testkey")
        self.assertIn("anthropic-version", [k.lower() for k in req.headers])

    @patch("scripts.validator.urllib.request.urlopen")
    def test_openrouter_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"data": {"label": "test-key"}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_llm_key("openrouter", "sk-or-testkey")
        self.assertTrue(ok)
        self.assertIn("OpenRouter", msg)
        req = mock_urlopen.call_args[0][0]
        self.assertIn("openrouter.ai/api/v1/auth/key", req.full_url)
        self.assertEqual(req.headers.get("Authorization"), "Bearer sk-or-testkey")

    @patch("scripts.validator.urllib.request.urlopen")
    def test_invalid_key_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.openai.com/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"error": {"message": "Incorrect API key provided"}}'),
        )

        ok, msg = validate_llm_key("openai", "invalid-key")
        self.assertFalse(ok)
        self.assertIn("Incorrect API key", msg)

    @patch("scripts.validator.urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("DNS resolution failure")

        ok, msg = validate_llm_key("gemini", "fake-key")
        self.assertFalse(ok)
        self.assertIn("DNS resolution failure", msg)

    def test_unsupported_provider(self):
        ok, msg = validate_llm_key("unknown_provider", "key")
        self.assertFalse(ok)
        self.assertIn("unsupported", msg.lower())


class TestWebhookValidation(unittest.TestCase):
    """Test suite for webhook and notification channel validation."""

    def test_telegram_missing_parameters(self):
        ok, msg = validate_webhook("telegram", "")
        self.assertFalse(ok)
        self.assertIn("token", msg.lower())

        ok, msg = validate_webhook("telegram", "12345:bot_token", chat_id=None)
        self.assertFalse(ok)
        self.assertIn("chat_id", msg.lower())

    @patch("scripts.validator.urllib.request.urlopen")
    def test_telegram_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"ok": True, "result": {"message_id": 100}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_webhook("telegram", "123456:ABC-DEF", chat_id="987654321")
        self.assertTrue(ok)
        self.assertIn("Telegram", msg)
        req = mock_urlopen.call_args[0][0]
        self.assertIn("api.telegram.org/bot123456:ABC-DEF/sendMessage", req.full_url)
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body.get("chat_id"), "987654321")

    @patch("scripts.validator.urllib.request.urlopen")
    def test_telegram_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.telegram.org/bot123/sendMessage",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"ok": false, "description": "chat not found"}'),
        )

        ok, msg = validate_webhook("telegram", "123:token", chat_id="invalid_chat")
        self.assertFalse(ok)
        self.assertIn("chat not found", msg)

    def test_discord_missing_url(self):
        ok, msg = validate_webhook("discord", "")
        self.assertFalse(ok)
        self.assertIn("url", msg.lower())

    @patch("scripts.validator.urllib.request.urlopen")
    def test_discord_success_204(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.read.return_value = b""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = validate_webhook("discord", "https://discord.com/api/webhooks/123/xyz")
        self.assertTrue(ok)
        self.assertIn("Discord", msg)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://discord.com/api/webhooks/123/xyz")
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("OmniPost", body.get("content", ""))

    @patch("scripts.validator.urllib.request.urlopen")
    def test_discord_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://discord.com/api/webhooks/123/xyz",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message": "Unknown Webhook"}'),
        )

        ok, msg = validate_webhook("discord", "https://discord.com/api/webhooks/123/xyz")
        self.assertFalse(ok)
        self.assertIn("Unknown Webhook", msg)

    def test_unsupported_webhook_service(self):
        ok, msg = validate_webhook("slack", "https://hooks.slack.com/services/xxx")
        self.assertFalse(ok)
        self.assertIn("unsupported", msg.lower())


if __name__ == "__main__":
    unittest.main()
