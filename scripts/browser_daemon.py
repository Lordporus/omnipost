"""Edge Browser Lifecycle Daemon & Auto-Healer.

Ensures Microsoft Edge is perpetually available on port 9444 for CDP automation.
If Edge is closed, terminated, or the machine reboots, this daemon launches Edge
in headless or background mode using the dedicated automation profile.
"""
from __future__ import annotations

import os
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
    is_headless = bool(cfg.get("headless", False) or os.environ.get("HEADLESS") == "1")
    if is_headless:
        cmd.append("--headless=new")

    is_container_or_linux = (
        sys.platform.startswith("linux")
        or os.environ.get("IS_DOCKER") == "1"
        or is_headless
    )
    if is_container_or_linux:
        for flag in ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
            if flag not in cmd:
                cmd.append(flag)

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
