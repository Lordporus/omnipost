"""Desktop Notifications & Operator Alerts for OmniPost.

Delivers system toast notifications on Windows or console alerts
when posts are published or when a platform requires re-authentication.
Also integrates remote webhook dispatching (Telegram and Discord) and
fast-fail session expiry alerts for headless Docker and VPS deployments.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any

try:
    from scripts.notify_webhook import dispatch_webhook, send_session_expired_alert
except ImportError:
    from notify_webhook import dispatch_webhook, send_session_expired_alert


def send_notification(title: str, message: str, webhook: bool = False) -> None:
    """Dispatches a Windows PowerShell Toast notification or logs fallback."""
    ps_cmd = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName('text')
    $textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
    $textNodes.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('OmniPost Syndicate').Show($toast)
    """
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        print(f"[NOTIFY] {title}: {message}")

    if webhook:
        try:
            dispatch_webhook("notification", title, message)
        except Exception:
            pass


def notify_publish(slot: str, results: dict[str, Any]) -> None:
    """Formats and dispatches publication summary across desktop toast and remote webhooks."""
    successful = [p.upper() for p, res in (results or {}).items() if res.get("success")]
    failed = [p.upper() for p, res in (results or {}).items() if not res.get("success")]

    if successful:
        title = "OmniPost V2 Published"
        msg = f"Slot {slot} published to: {', '.join(successful)}"
        if failed:
            msg += f" (Failed: {', '.join(failed)})"
        event_type = "publish_partial" if failed else "publish_success"
    elif failed:
        title = "OmniPost Publish Warning"
        msg = f"Slot {slot} failed on: {', '.join(failed)}"
        event_type = "publish_failure"
    else:
        title = "OmniPost Publish Info"
        msg = f"Slot {slot} had no publishing targets"
        event_type = "publish_info"

    # 1. Desktop toast notification
    send_notification(title, msg)

    # 2. Remote webhook notification (Telegram / Discord)
    try:
        dispatch_webhook(
            event_type=event_type,
            title=title,
            message=msg,
            metadata={"slot": slot, "successful": successful, "failed": failed},
        )
    except Exception as exc:
        print(f"[NOTIFY] Webhook dispatch error: {exc}", file=sys.stderr)

    # 3. Check for platform session expiration / fast-fail alerts
    for platform, res in (results or {}).items():
        if not res.get("success"):
            err = str(res.get("error", "")).lower()
            if any(k in err for k in ("session expired", "session", "expired", "re-login", "unauthorized", "auth")):
                action = (
                    res.get("action_required")
                    or f"Operator re-login required for {platform.upper()} in automation profile"
                )
                try:
                    send_session_expired_alert(platform=platform, action_required=action)
                except Exception as exc:
                    print(f"[ALERT] Session alert error: {exc}", file=sys.stderr)
