# Task 1 Brief: Edge Browser Lifecycle Daemon & Auto-Healer

## Goal
Implement `scripts/browser_daemon.py` and `tests/test_browser_daemon.py`.
Ensures Microsoft Edge is perpetually available on port 9444 for CDP automation.
If Edge is closed, terminated, or the machine reboots, this daemon launches Edge in background mode using the dedicated automation profile `C:\Users\Sachin\.tweetytweets\edge-profile`.

## Files
- Create: `scripts/browser_daemon.py`
- Test: `tests/test_browser_daemon.py`

## Interfaces
- Consumes: `settings.get_browser_config()` from `scripts/settings.py`
- Produces:
  - `is_browser_running(port: int = 9444, timeout: float = 2.0) -> bool`
  - `ensure_browser_running(max_wait_seconds: int = 10) -> bool`

## Steps to Execute (TDD)
1. Write the test `tests/test_browser_daemon.py`:
```python
from unittest.mock import patch, MagicMock
from scripts.browser_daemon import is_browser_running, ensure_browser_running


def test_is_browser_running_success():
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_open.return_value.__enter__.return_value = mock_resp
        assert is_browser_running(port=9444) is True


def test_is_browser_running_failure():
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert is_browser_running(port=9444) is False


def test_ensure_browser_running_already_active():
    with patch("scripts.browser_daemon.is_browser_running", return_value=True):
        assert ensure_browser_running() is True


def test_ensure_browser_running_spawns_process():
    with patch("scripts.browser_daemon.is_browser_running", side_effect=[False, True]), \
         patch("subprocess.Popen") as mock_popen:
        assert ensure_browser_running() is True
        mock_popen.assert_called_once()
```
2. Run test to verify it fails:
`C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_browser_daemon.py`
3. Implement `scripts/browser_daemon.py`:
```python
"""Edge Browser Lifecycle Daemon & Auto-Healer.

Ensures Microsoft Edge is perpetually available on port 9444 for CDP automation.
If Edge is closed, terminated, or the machine reboots, this daemon launches Edge
in headless or background mode using the dedicated automation profile.
"""
from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import settings
except ImportError:
    from scripts import settings


def is_browser_running(port: int = 9444, timeout: float = 2.0) -> bool:
    """Checks if the CDP endpoint is responsive on the designated port."""
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.getcode() == 200
    except Exception:
        return False


def ensure_browser_running(max_wait_seconds: int = 10) -> bool:
    """Checks if Edge is running; if not, spawns it and waits for CDP readiness."""
    cfg = settings.get_browser_config()
    port = cfg.get("port", 9444)
    if is_browser_running(port=port):
        return True

    exe = cfg.get("chrome_path") or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    profile = cfg.get("profile_dir") or r"C:\Users\Sachin\.tweetytweets\edge-profile"
    
    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if cfg.get("headless", False):
        cmd.append("--headless=new")

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        print(f"[DAEMON] Failed to spawn Edge browser: {exc}", file=sys.stderr)
        return False

    start = time.time()
    while time.time() - start < max_wait_seconds:
        time.sleep(0.5)
        if is_browser_running(port=port):
            return True

    return False


if __name__ == "__main__":
    if ensure_browser_running():
        print("[DAEMON] Microsoft Edge CDP automation session is ONLINE on port 9444.")
        sys.exit(0)
    else:
        print("[DAEMON] Failed to start Edge CDP session.", file=sys.stderr)
        sys.exit(1)
```
4. Run test to verify it passes.
5. Commit:
`git add scripts/browser_daemon.py tests/test_browser_daemon.py`
`git commit -m "feat(daemon): add Edge browser lifecycle daemon and auto-healer"`
6. Write report to `.superpowers/sdd/production-schedule-plan/task-1-report.md`.
