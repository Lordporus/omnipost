"""Tests for remote CDP browser support (Docker -> Windows Edge)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from scripts import browser


def test_remote_host_rewrites_localhost_websocket(monkeypatch):
    monkeypatch.setenv("BROWSER_HOST", "192.168.65.254")
    port = browser._port()

    assert browser._is_remote() is True
    assert browser._base() == f"http://192.168.65.254:{port}"
    assert browser._rewrite_ws(
        f"ws://127.0.0.1:{port}/devtools/page/abc"
    ) == f"ws://192.168.65.254:{port}/devtools/page/abc"


def test_remote_browser_translates_app_mount_to_host_path(monkeypatch):
    monkeypatch.setenv("BROWSER_HOST", "192.168.65.254")
    monkeypatch.setenv("BROWSER_HOST_PROJECT_ROOT", "C:/repo")

    assert browser.browser_file_path(
        "/app/scratch/cards/card_20261025_1600_card_1.png"
    ) == "C:/repo/scratch/cards/card_20261025_1600_card_1.png"


def test_threads_profile_target_navigates_from_home():
    tab = {
        "url": "https://www.threads.com/",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9444/devtools/page/abc",
    }
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.send = AsyncMock()

    with patch("scripts.browser.list_tabs", return_value=[tab]), \
         patch("scripts.browser.Session", return_value=session):
        ws = asyncio.run(
            browser.open_page("https://www.threads.com/@ig_lordporus")
        )

    assert ws == tab["webSocketDebuggerUrl"]
    session.send.assert_awaited_once_with(
        "Page.navigate", url="https://www.threads.com/@ig_lordporus"
    )
