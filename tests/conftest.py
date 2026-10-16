"""Global pytest fixtures and test isolation guardrails for OmniPost."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def isolate_webhooks(request):
    """Prevents tests from dispatching real webhook alerts to Telegram or Discord.
    
    Modules specifically dedicated to testing webhook formatting (e.g., test_notify_webhook.py)
    handle their own isolated mocks of urllib.request.urlopen. All other modules (such as
    test_notify.py, test_retry_isolation.py, test_pipeline.py) have their webhook dispatchers
    safely intercepted.
    """
    if "test_notify_webhook" in request.module.__name__:
        yield
        return

    with patch("scripts.notify_webhook.dispatch_webhook", return_value=True) as mock_dispatch:
        with patch("scripts.notify.dispatch_webhook", return_value=True):
            with patch("scripts.notify_webhook.send_session_expired_alert", return_value=True):
                with patch("scripts.notify.send_session_expired_alert", return_value=True):
                    yield
