# Task 5 Brief: Desktop Notification & Feedback Dispatcher

## Goal
Implement `scripts/notify.py` and `tests/test_notify.py`.
Delivers system toast notifications on Windows or console alerts when posts are published or when a platform requires re-authentication.

## Files
- Create: `scripts/notify.py`
- Test: `tests/test_notify.py`

## Interfaces
- Consumes: Platform results from `autoposter.py`
- Produces:
  - `send_notification(title: str, message: str) -> None`
  - `notify_publish(slot: str, results: dict[str, Any]) -> None`

## Steps to Execute (TDD)
1. Write the test `tests/test_notify.py`:
```python
from unittest.mock import patch
from scripts.notify import notify_publish


def test_notify_publish_success():
    results = {
        "x": {"success": True, "url": "https://x.com/post/1"},
        "bluesky": {"success": True, "url": "https://bsky.app/post/2"},
    }
    with patch("scripts.notify.send_notification") as mock_notify:
        notify_publish("16:00", results)
        mock_notify.assert_called_once()
        assert "Published" in mock_notify.call_args[0][0]
```
2. Run test to verify it fails:
`C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_notify.py`
3. Implement `scripts/notify.py`:
```python
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
```
4. Run test to verify it passes.
5. Commit:
`git add scripts/notify.py tests/test_notify.py`
`git commit -m "feat(notify): add desktop toast notification and alert dispatcher"`
6. Write report to `.superpowers/sdd/production-schedule-plan/task-5-report.md`.
