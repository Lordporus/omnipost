"""Tests for OmniPost Webhook Notifier & Fast-Fail Alerts."""
from __future__ import annotations

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from scripts.notify_webhook import (
    DEFAULT_TIMEOUT,
    _load_webhook_proxy,
    dispatch_webhook,
    send_session_expired_alert,
)


@pytest.fixture(autouse=True)
def isolate_env_fallback():
    with patch("scripts.notify_webhook._read_env_fallback", return_value={}):
        yield


def test_telegram_webhook_dispatch():
    """Verifies POST payload formatting to Telegram Bot API."""
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN",
        "TELEGRAM_CHAT_ID": "987654321",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            success = dispatch_webhook(
                event_type="publish_success",
                title="OmniPost V2 Published",
                message="Slot 16:00 published to: X, BLUESKY",
                metadata={"slot": "16:00", "count": 2},
            )

            assert success is True
            assert mock_urlopen.call_count == 1
            req = mock_urlopen.call_args[0][0]
            assert req.full_url == "https://api.telegram.org/bot123456:TEST_TOKEN/sendMessage"
            assert req.method == "POST"
            assert req.headers.get("Content-type") == "application/json"

            body = json.loads(req.data.decode("utf-8"))
            assert body["chat_id"] == "987654321"
            assert "OmniPost V2 Published" in body["text"]
            assert "Slot 16:00 published to: X, BLUESKY" in body["text"]
            assert "slot: 16:00" in body["text"]


def test_discord_webhook_dispatch():
    """Verifies rich embed JSON structure to Discord webhook URL."""
    env = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/token_abc",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b""
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            success = dispatch_webhook(
                event_type="publish_success",
                title="OmniPost V2 Published",
                message="Slot 16:00 published to: X",
                metadata={"slot": "16:00", "platform": "x"},
            )

            assert success is True
            assert mock_urlopen.call_count == 1
            req = mock_urlopen.call_args[0][0]
            assert req.full_url == "https://discord.com/api/webhooks/123/token_abc"
            assert req.method == "POST"
            assert req.headers.get("Content-type") == "application/json"

            body = json.loads(req.data.decode("utf-8"))
            assert "embeds" in body
            assert len(body["embeds"]) == 1
            embed = body["embeds"][0]
            assert embed["title"] == "OmniPost V2 Published"
            assert embed["description"] == "Slot 16:00 published to: X"
            assert "color" in embed
            assert isinstance(embed["color"], int)

            fields = {f["name"]: f["value"] for f in embed.get("fields", [])}
            assert fields.get("slot") == "16:00"
            assert fields.get("platform") == "x"


def test_session_expired_alert():
    """Verifies formatting and dispatching of fast-fail alert when cookies/tokens expire."""
    with patch("scripts.notify_webhook.dispatch_webhook") as mock_dispatch:
        mock_dispatch.return_value = True

        result = send_session_expired_alert(
            platform="linkedin",
            action_required="Operator re-login required in automation profile",
        )

        assert result is True
        mock_dispatch.assert_called_once()
        args, kwargs = mock_dispatch.call_args
        event_type = kwargs.get("event_type", args[0] if len(args) > 0 else "")
        title = kwargs.get("title", args[1] if len(args) > 1 else "")
        message = kwargs.get("message", args[2] if len(args) > 2 else "")
        metadata = kwargs.get("metadata", args[3] if len(args) > 3 else {})

        assert event_type == "session_expired"
        assert "LINKEDIN" in title.upper()
        assert "SESSION EXPIRED" in title.upper()
        assert "Operator re-login required" in message
        assert metadata.get("platform") == "linkedin"


def test_webhook_unconfigured_graceful():
    """Returns False cleanly without errors when no webhook credentials are set."""
    with patch.dict(os.environ, {}, clear=True):
        # Even if config.json has no webhooks or doesn't exist
        with patch("scripts.notify_webhook._load_webhook_credentials", return_value={"telegram": None, "discord": None}):
            success = dispatch_webhook(
                event_type="test",
                title="Test Title",
                message="Test Message",
            )
            assert success is False


def test_webhook_network_error_graceful():
    """Catches urllib/network errors without raising exceptions or breaking the publishing loop."""
    env = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/token_abc",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            success = dispatch_webhook(
                event_type="error",
                title="Error Title",
                message="Network failure test",
            )
            assert success is False


def test_webhook_timeout_graceful():
    """Catches timeout exceptions without raising."""
    env = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/token_abc",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            success = dispatch_webhook(
                event_type="error",
                title="Timeout Title",
                message="Timeout test",
            )
            assert success is False


def test_empty_env_strings_treated_as_unset():
    """Confirms empty strings in environment variables do not trigger dispatches."""
    env = {
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "  ",
        "DISCORD_WEBHOOK_URL": "",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.urlopen") as mock_urlopen:
            success = dispatch_webhook(
                event_type="test",
                title="Empty Env Test",
                message="Should not dispatch",
            )
            assert success is False
            assert mock_urlopen.call_count == 0


def test_default_timeout_is_five_seconds():
    """Verifies that DEFAULT_TIMEOUT is strictly set to 5.0 seconds and passed to urlopen."""
    assert DEFAULT_TIMEOUT == 5.0

    env = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/token_abc",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b""
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            dispatch_webhook(
                event_type="test",
                title="Timeout Check",
                message="Checking default timeout parameter",
            )

            assert mock_urlopen.call_count == 1
            _, kwargs = mock_urlopen.call_args
            assert kwargs.get("timeout") == 5.0


def test_proxy_from_env_vars():
    """Verifies proxy configuration via HTTPS_PROXY or HTTP_PROXY environment variables."""
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN",
        "TELEGRAM_CHAT_ID": "987654321",
        "HTTPS_PROXY": "http://127.0.0.1:8080",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("urllib.request.build_opener") as mock_build_opener:
            mock_opener = MagicMock()
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
            mock_opener.open.return_value.__enter__.return_value = mock_resp
            mock_build_opener.return_value = mock_opener

            success = dispatch_webhook(
                event_type="publish_success",
                title="Proxy Test",
                message="Testing proxy dispatch",
            )

            assert success is True
            assert mock_build_opener.call_count == 1
            handler = mock_build_opener.call_args[0][0]
            assert isinstance(handler, urllib.request.ProxyHandler)
            assert handler.proxies == {
                "http": "http://127.0.0.1:8080",
                "https": "http://127.0.0.1:8080",
            }
            mock_opener.open.assert_called_once()
            _, kwargs = mock_opener.open.call_args
            assert kwargs.get("timeout") == 5.0


def test_proxy_from_config_json(tmp_path):
    """Verifies proxy fallback to config.json when env vars are unset."""
    env = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/token_abc",
    }
    config_data = {
        "notifications": {
            "proxy": "http://corporate.proxy.internal:3128"
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    with patch.dict(os.environ, env, clear=True):
        with patch("scripts.notify_webhook.ROOT", tmp_path):
            assert _load_webhook_proxy() == "http://corporate.proxy.internal:3128"
            with patch("urllib.request.build_opener") as mock_build_opener:
                mock_opener = MagicMock()
                mock_resp = MagicMock()
                mock_resp.read.return_value = b""
                mock_opener.open.return_value.__enter__.return_value = mock_resp
                mock_build_opener.return_value = mock_opener

                success = dispatch_webhook(
                    event_type="info",
                    title="Config Proxy Test",
                    message="Testing config proxy",
                )
                assert success is True
                assert mock_build_opener.call_count == 1
                handler = mock_build_opener.call_args[0][0]
                assert handler.proxies == {
                    "http": "http://corporate.proxy.internal:3128",
                    "https": "http://corporate.proxy.internal:3128",
                }


def test_proxy_whitespace_or_empty_ignored():
    """Verifies whitespace or empty strings in proxy environment variables are ignored."""
    env = {
        "HTTPS_PROXY": "   ",
        "HTTP_PROXY": "",
    }
    with patch.dict(os.environ, env, clear=True):
        assert _load_webhook_proxy() == ""


