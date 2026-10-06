from unittest.mock import patch
from scripts.notify import notify_publish, send_notification


def test_notify_publish_success():
    results = {
        "x": {"success": True, "url": "https://x.com/post/1"},
        "bluesky": {"success": True, "url": "https://bsky.app/post/2"},
    }
    with patch("scripts.notify.send_notification") as mock_notify:
        notify_publish("16:00", results)
        mock_notify.assert_called_once()
        assert "Published" in mock_notify.call_args[0][0]
        assert "X, BLUESKY" in mock_notify.call_args[0][1]


def test_notify_publish_failure():
    results = {
        "linkedin": {"success": False, "error": "Session expired"},
    }
    with patch("scripts.notify.send_notification") as mock_notify:
        notify_publish("16:00", results)
        mock_notify.assert_called_once()
        assert "Warning" in mock_notify.call_args[0][0]
        assert "LINKEDIN" in mock_notify.call_args[0][1]


def test_notify_publish_partial():
    results = {
        "x": {"success": True, "url": "https://x.com/post/1"},
        "threads": {"success": False, "error": "Network timeout"},
    }
    with patch("scripts.notify.send_notification") as mock_notify:
        notify_publish("16:00", results)
        mock_notify.assert_called_once()
        assert "Published" in mock_notify.call_args[0][0]
        assert "X" in mock_notify.call_args[0][1]
        assert "THREADS" in mock_notify.call_args[0][1]


def test_notify_publish_triggers_webhook():
    results = {
        "x": {"success": True, "url": "https://x.com/post/1"},
    }
    with patch("scripts.notify.send_notification"):
        with patch("scripts.notify.dispatch_webhook") as mock_webhook:
            notify_publish("16:00", results)
            mock_webhook.assert_called_once()
            args, kwargs = mock_webhook.call_args
            assert kwargs.get("event_type") == "publish_success"
            assert kwargs.get("metadata", {}).get("slot") == "16:00"


def test_notify_publish_triggers_session_alert():
    results = {
        "linkedin": {"success": False, "error": "Session expired: cookies invalid"},
    }
    with patch("scripts.notify.send_notification"):
        with patch("scripts.notify.send_session_expired_alert") as mock_alert:
            notify_publish("16:00", results)
            mock_alert.assert_called_once()
            _, kwargs = mock_alert.call_args
            assert kwargs.get("platform") == "linkedin"
            assert "re-login" in kwargs.get("action_required", "").lower()


def test_send_notification_webhook_flag():
    with patch("subprocess.run"):
        with patch("scripts.notify.dispatch_webhook") as mock_webhook:
            send_notification("Test Title", "Test Message", webhook=True)
            mock_webhook.assert_called_once_with("notification", "Test Title", "Test Message")
