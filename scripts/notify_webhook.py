"""Remote Webhook Notification Dispatcher & Fast-Fail Session Alerting for OmniPost.

Supports headless webhook alerts for Docker and VPS deployments via Telegram Bot API
and Discord Webhooks, providing real-time publication notifications and immediate
session-expired alerts for operator intervention.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = 8.0
USER_AGENT = "OmniPost-Notifier/1.0"


def _read_env_fallback() -> dict[str, str]:
    """Parse key=value pairs from .env if present in root."""
    env_path = ROOT / ".env"
    if not env_path.exists() or not env_path.is_file():
        return {}
    res: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                res[k.strip()] = v.strip().strip("\"'")
    except Exception:
        pass
    return res


def _load_webhook_credentials() -> dict[str, Any]:
    """Resolves Telegram and Discord webhook credentials from environment or .env file."""
    env_fallback = _read_env_fallback()

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN") or env_fallback.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID") or env_fallback.get("TELEGRAM_CHAT_ID", "").strip()

    dc_url = os.environ.get("DISCORD_WEBHOOK_URL") or env_fallback.get("DISCORD_WEBHOOK_URL", "").strip()

    telegram_config = None
    if tg_token and tg_chat_id:
        telegram_config = {
            "token": tg_token,
            "chat_id": tg_chat_id,
        }

    discord_config = None
    if dc_url and (dc_url.startswith("http://") or dc_url.startswith("https://")):
        discord_config = {
            "url": dc_url,
        }

    return {
        "telegram": telegram_config,
        "discord": discord_config,
    }


def _dispatch_telegram(
    token: str,
    chat_id: str,
    title: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """Dispatches formatted message to Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    text_parts = [f"📢 {title}", "", message]
    if metadata:
        text_parts.append("")
        for k, v in metadata.items():
            text_parts.append(f"• {k}: {v}")
    full_text = "\n".join(text_parts).strip()

    payload = json.dumps({
        "chat_id": str(chat_id),
        "text": full_text,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            parsed = json.loads(data.decode("utf-8")) if data else {}
            if parsed.get("ok", True):
                return True
            desc = parsed.get("description", "Unknown Telegram error")
            print(f"[NOTIFY] Telegram warning: {desc}", file=sys.stderr)
            return False
    except Exception as exc:
        print(f"[NOTIFY] Telegram webhook error: {exc}", file=sys.stderr)
        return False


def _dispatch_discord(
    url: str,
    event_type: str,
    title: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """Dispatches rich embed JSON payload to Discord webhook URL."""
    # Color palette: Red for errors/alerts, Green for success, Blue for general info
    ev_lower = (event_type or "").lower()
    if any(k in ev_lower for k in ("error", "fail", "expired", "warn")):
        color = 0xEF4444  # Red
    elif any(k in ev_lower for k in ("success", "published")):
        color = 0x10B981  # Green
    else:
        color = 0x3B82F6  # Blue

    embed: dict[str, Any] = {
        "title": title,
        "description": message,
        "color": color,
    }

    if metadata:
        fields = []
        for k, v in metadata.items():
            fields.append({
                "name": str(k),
                "value": str(v),
                "inline": True,
            })
        embed["fields"] = fields

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read()
            return True
    except Exception as exc:
        print(f"[NOTIFY] Discord webhook error: {exc}", file=sys.stderr)
        return False


def dispatch_webhook(
    event_type: str,
    title: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """Dispatches alerts to configured Telegram Bot or Discord Webhook.

    Returns True if at least one notification was successfully dispatched, False otherwise.
    Never raises exceptions, ensuring publishing loop continuity in headless environments.
    """
    creds = _load_webhook_credentials()
    tg_config = creds.get("telegram")
    dc_config = creds.get("discord")

    if not tg_config and not dc_config:
        return False

    success = False

    if tg_config:
        tg_ok = _dispatch_telegram(
            token=tg_config["token"],
            chat_id=tg_config["chat_id"],
            title=title,
            message=message,
            metadata=metadata,
            timeout=timeout,
        )
        if tg_ok:
            success = True

    if dc_config:
        dc_ok = _dispatch_discord(
            url=dc_config["url"],
            event_type=event_type,
            title=title,
            message=message,
            metadata=metadata,
            timeout=timeout,
        )
        if dc_ok:
            success = True

    return success


def send_session_expired_alert(
    platform: str,
    action_required: str = "Operator re-login required in automation profile",
) -> bool:
    """Dispatches high-priority fast-fail alert when platform cookies or session tokens expire."""
    plat_upper = (platform or "Unknown").upper()
    title = f"🚨 OmniPost Alert: Session Expired for {plat_upper}"
    message = (
        f"Authentication session expired on {plat_upper}.\n"
        f"Action Required: {action_required}"
    )
    metadata = {
        "platform": platform,
        "action_required": action_required,
        "priority": "critical",
        "alert": "session_expired",
    }

    # Console warning for immediate CLI/Docker logs visibility
    print(
        f"[ALERT] Critical: Session expired for {plat_upper}. {action_required}",
        file=sys.stderr,
    )

    return dispatch_webhook(
        event_type="session_expired",
        title=title,
        message=message,
        metadata=metadata,
    )
