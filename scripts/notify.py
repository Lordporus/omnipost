"""Desktop Notifications & Operator Alerts for OmniPost.

Delivers system toast notifications on Windows or console alerts
when posts are published or when a platform requires re-authentication.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def send_notification(title: str, message: str) -> None:
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


def notify_publish(slot: str, results: dict[str, Any]) -> None:
    """Formats and dispatches publication summary."""
    successful = [p.upper() for p, res in results.items() if res.get("success")]
    failed = [p.upper() for p, res in results.items() if not res.get("success")]

    if successful:
        msg = f"Slot {slot} published to: {', '.join(successful)}"
        if failed:
            msg += f" (Failed: {', '.join(failed)})"
        send_notification("OmniPost V2 Published", msg)
    elif failed:
        send_notification("OmniPost Publish Warning", f"Slot {slot} failed on: {', '.join(failed)}")
