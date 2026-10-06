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
