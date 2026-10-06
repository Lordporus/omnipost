# Task 4 Brief: Remote Webhook Dispatcher & Fast-Fail Alerts

## Goal
Implement `scripts/notify_webhook.py`, update `scripts/notify.py` to trigger webhooks alongside desktop toasts, and write `tests/test_notify_webhook.py`.
Provides headless notification dispatching (Telegram and Discord) for Docker and VPS deployments, with fast-fail session expiry alerts.

## Files
- **Create:** `scripts/notify_webhook.py`
- **Modify:** `scripts/notify.py`
- **Create:** `tests/test_notify_webhook.py`

## Interfaces & Contracts

```python
from typing import Any

def dispatch_webhook(event_type: str, title: str, message: str, metadata: dict[str, Any] | None = None, timeout: float = 8.0) -> bool:
    """Dispatches alerts to configured Telegram Bot or Discord Webhook. Returns True if at least one succeeded."""

def send_session_expired_alert(platform: str, action_required: str = "Operator re-login required in automation profile") -> bool:
    """Dispatches high-priority fast-fail alert when platform cookies or session tokens expire."""
```

## TDD Steps
1. Write `tests/test_notify_webhook.py` covering:
   - `test_telegram_webhook_dispatch`: verifies POST format to Telegram API.
   - `test_discord_webhook_dispatch`: verifies embed JSON payload to Discord webhook.
   - `test_session_expired_alert`: verifies formatting of critical session expiry warning.
   - `test_webhook_unconfigured_graceful`: returns False without error when no webhooks configured.
   - `test_webhook_timeout_graceful`: catches urllib exceptions without raising.
2. Run test to verify it fails:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_notify_webhook.py`
3. Implement `scripts/notify_webhook.py`.
4. Update `scripts/notify.py` to call `dispatch_webhook` inside `notify_publish` and `send_notification`.
5. Run tests to verify all pass:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_notify_webhook.py tests/test_notify.py`
6. Commit:
   `git add scripts/notify_webhook.py scripts/notify.py tests/test_notify_webhook.py`
   `git commit -m "feat(webhook): add remote Telegram and Discord webhook notifications and session alerts"`
7. Write report to `.superpowers/sdd/onboarding-deployment-execution-plan/task-4-report.md`.
