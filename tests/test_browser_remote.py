"""Tests for remote CDP browser support (Docker -> Windows Edge)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from scripts import browser


def test_remote_host_rewrites_localhost_websocket(monkeypatch):
    monkeypatch.setenv("BROWSER_HOST", "192.168.65.254")
    # config.json is gitignored, so CI has none and _port() falls back to 9222.
    monkeypatch.setattr(browser, "_browser_config", lambda: {"port": 9444})

    assert browser._is_remote() is True
    assert browser._base() == "http://192.168.65.254:9444"
    assert browser._rewrite_ws(
        "ws://127.0.0.1:9444/devtools/page/abc"
    ) == "ws://192.168.65.254:9444/devtools/page/abc"


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
    session.send.assert_any_await(
        "Page.navigate", url="https://www.threads.com/@ig_lordporus"
    )


def test_open_page_activates_reused_tab():
    """A reused tab must be foregrounded before navigating.

    A background tab renders both composers in a degraded layout (X: empty
    dialog shells, Threads: 0x0 modal), which breaks every publish.
    """
    tab = {
        "url": "https://www.threads.com/",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9444/devtools/page/abc",
    }
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    calls: list[str] = []

    async def _send(method, **_kwargs):
        calls.append(method)

    session.send = _send

    with patch("scripts.browser.list_tabs", return_value=[tab]), \
         patch("scripts.browser.Session", return_value=session):
        asyncio.run(browser.open_page("https://www.threads.com/@ig_lordporus"))

    assert calls == ["Page.bringToFront", "Page.navigate"]


def test_open_page_activates_tab_already_on_target_url():
    """Reuse without navigation must still foreground the tab."""
    tab = {
        "url": "https://www.threads.com/",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9444/devtools/page/abc",
    }
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    calls: list[str] = []

    async def _send(method, **_kwargs):
        calls.append(method)

    session.send = _send

    with patch("scripts.browser.list_tabs", return_value=[tab]), \
         patch("scripts.browser.Session", return_value=session):
        ws = asyncio.run(browser.open_page("https://www.threads.com/"))

    assert ws == tab["webSocketDebuggerUrl"]
    assert calls == ["Page.bringToFront"]
