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
DEFAULT_TIMEOUT = 5.0
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

    def _get_val(key: str) -> str:
        if key in os.environ:
            v = os.environ[key]
            return v.strip() if v else ""
        v = env_fallback.get(key, "")
        return v.strip() if v else ""

    tg_token = _get_val("TELEGRAM_BOT_TOKEN")
    tg_chat_id = _get_val("TELEGRAM_CHAT_ID")
    dc_url = _get_val("DISCORD_WEBHOOK_URL")

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


def _load_webhook_proxy() -> str:
    """Resolves proxy URL from HTTPS_PROXY/HTTP_PROXY env vars or config.json.

    Treats empty string or whitespace as unset/falsy.
    """
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var)
        if val and val.strip():
            return val.strip()

    config_path = ROOT / "config.json"
    if config_path.exists() and config_path.is_file():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            notif = cfg.get("notifications", {})
            proxy = (
                notif.get("proxy")
                or notif.get("webhook_proxy")
                or cfg.get("webhook_proxy")
                or cfg.get("proxy")
            )
            if isinstance(proxy, str) and proxy.strip():
                return proxy.strip()
        except Exception:
            pass

    return ""


def _urlopen(
    req: urllib.request.Request,
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
):
    """Executes urllib request, using ProxyHandler when proxy is configured."""
    proxy_url = proxy if proxy is not None else _load_webhook_proxy()
    if proxy_url and proxy_url.strip():
        p = proxy_url.strip()
        proxy_handler = urllib.request.ProxyHandler({"http": p, "https": p})
        opener = urllib.request.build_opener(proxy_handler)
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _dispatch_telegram(
    token: str,
    chat_id: str,
    title: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
) -> bool:
    """Dispatches formatted message to Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    icon = "⚠️" if any(k in title.lower() for k in ("partial", "fail", "warn", "error")) else "📢"
    text_parts = [f"{icon} {title}", "", message]
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
        with _urlopen(req, timeout=timeout, proxy=proxy) as resp:
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
    proxy: str | None = None,
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
        with _urlopen(req, timeout=timeout, proxy=proxy) as resp:
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
    proxy: str | None = None,
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
            proxy=proxy,
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
            proxy=proxy,
        )
        if dc_ok:
            success = True

    return success


def send_session_expired_alert(
    platform: str,
    action_required: str = "Operator re-login required in automation profile",
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
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
        timeout=timeout,
        proxy=proxy,
    )


def format_summary_card(
    results: dict[str, Any],
    slot: str,
    total_time: float = 0.0,
    handles: dict[str, str] | None = None,
) -> str:
    """Formats an executive multi-platform summary card for Telegram / Discord."""
    handles = handles or {}
    lines = [
        "🚀 OmniPost: Daily Drop Completed!",
        f"📅 Slot: {slot}",
        "",
    ]
    error_count = 0
    plat_names = {
        "x": "X (Twitter)",
        "bluesky": "Bluesky",
        "threads": "Threads",
        "linkedin": "LinkedIn",
    }
    for plat_key, r in results.items():
        name = plat_names.get(plat_key.lower(), plat_key.upper())
        handle = handles.get(plat_key.lower(), "")
        handle_str = f": {handle}" if handle else ""

        success = getattr(r, "success", False) if hasattr(r, "success") else bool(r.get("success"))
        verified = (
            bool(getattr(r, "verified", success))
            if hasattr(r, "success")
            else bool(r.get("verified", success))
        )
        url = getattr(r, "url", None) if hasattr(r, "url") else r.get("url")
        err = getattr(r, "error", None) if hasattr(r, "error") else r.get("error")

        if success and verified:
            lines.append(f"✅ {name}{handle_str}")
            if url:
                lines.append(f"   🔗 {url}")
            else:
                lines.append(f"   🔗 Verified live on feed")
        elif success:
            error_count += 1
            lines.append(f"⚠️ {name}{handle_str}")
            lines.append(f"   ⚠️ Submitted but unverified: {err or 'read-back failed'}")
        elif err == "network_timeout":
            error_count += 1
            lines.append(f"⚠️ {name}{handle_str}")
            lines.append("   ⚠️ Network timeout (deferred check)")
        else:
            error_count += 1
            lines.append(f"❌ {name}{handle_str}")
            lines.append(f"   ❌ Failed: {err or 'Unknown error'}")

    t_str = f"{int(total_time)}s" if total_time > 0 else "<30s"
    lines.append("")
    lines.append(f"🛡️ Guardrails Passed | {error_count} Errors | Total Time: {t_str}")
    return "\n".join(lines).strip()


def dispatch_summary_card(
    results: dict[str, Any],
    slot: str,
    total_time: float = 0.0,
    handles: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    proxy: str | None = None,
) -> bool:
    """Dispatches the rich multi-platform executive card to configured webhooks."""
    card = format_summary_card(results=results, slot=slot, total_time=total_time, handles=handles)
    return dispatch_webhook(
        event_type="summary",
        title="OmniPost Executive Report",
        message=card,
        timeout=timeout,
        proxy=proxy,
    )

