"""Browser Lifecycle Daemon & Auto-Healer for OmniPost.

Ensures Chrome or Microsoft Edge is perpetually available on port 9444 for CDP automation.
If the browser is closed or terminated, this daemon launches it in background mode
using the dedicated automation profile and clears stale lock files.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
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


def stop_browser_processes(port: int = 9444) -> None:
    """Stops any processes holding the CDP port."""
    if sys.platform == "win32":
        cmd_ps = (
            f"Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.CommandLine -like '*{port}*' -and ($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') }} | "
            f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd_ps], capture_output=True)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["pkill", "-f", f"--remote-debugging-port={port}"], capture_output=True)
        except Exception:
            pass
    time.sleep(1.0)


def ensure_browser_running(max_wait_seconds: int = 15) -> bool:
    """Checks if browser is running; if not, spawns it and waits for CDP readiness."""
    cfg = settings.get_browser_config()
    port = cfg.get("port", 9444)
    if is_browser_running(port=port):
        return True

    exe = (
        cfg.get("chrome_path")
        or os.environ.get("CHROME_PATH")
        or (str(settings.find_chrome()) if settings.find_chrome() else None)
        or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )
    if not Path(exe).exists() and sys.platform == "win32":
        exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    try:
        home_dir = Path.home()
        if str(home_dir) == "~":
            home_dir = Path(".")
    except Exception:
        home_dir = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")

    legacy_profile = home_dir / ".tweetytweets" / "edge-profile"
    default_profile = home_dir / ".omnipost" / "edge-profile"
    try:
        if legacy_profile.exists() and not default_profile.exists():
            profile_path = str(legacy_profile)
        else:
            profile_path = str(default_profile)
    except OSError:
        profile_path = str(default_profile)
    profile = (
        cfg.get("profile_dir")
        or os.environ.get("BROWSER_PROFILE")
        or profile_path
    )
    prof_p = Path(profile)
    try:
        prof_p.mkdir(parents=True, exist_ok=True)
        for f in prof_p.glob("Singleton*"):
            try:
                f.unlink()
            except Exception:
                pass
    except Exception:
        pass

    is_headless = bool(cfg.get("headless", False) or os.environ.get("HEADLESS") == "1")
    is_container_or_linux = (
        sys.platform.startswith("linux")
        or os.environ.get("IS_DOCKER") == "1"
        or is_headless
    )

    # On Windows desktop (interactive user session), launch with WinSta0 desktop session for UI access
    if sys.platform == "win32" and not is_container_or_linux:
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32

            class STARTUPINFO(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR),
                    ('lpDesktop', wintypes.LPWSTR), ('lpTitle', wintypes.LPWSTR),
                    ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                    ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD),
                    ('dwXCountChars', wintypes.DWORD), ('dwYCountChars', wintypes.DWORD),
                    ('dwFillAttribute', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                    ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
                    ('lpReserved2', ctypes.c_void_p), ('hStdInput', wintypes.HANDLE),
                    ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE),
                ]

            class PROCESS_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                    ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD),
                ]

            si = STARTUPINFO()
            si.cb = ctypes.sizeof(STARTUPINFO)
            si.lpDesktop = 'WinSta0\\Default'
            si.dwFlags = 1
            si.wShowWindow = 1
            pi = PROCESS_INFORMATION()

            cmd_str = (
                f'"{exe}" '
                f'--remote-debugging-port={port} '
                f'--remote-allow-origins=* '
                f'--user-data-dir="{profile}" '
                f'--new-window '
                f'--window-size=1280,800 '
                f'--window-position=50,50 '
                f'--no-first-run '
                f'--no-default-browser-check '
                f'--disable-background-mode '
                f'"https://x.com/home"'
            )
            ret = kernel32.CreateProcessW(
                None, cmd_str, None, None, False, 0, None, None,
                ctypes.byref(si), ctypes.byref(pi)
            )
            if ret:
                start = time.time()
                while time.time() - start < max_wait_seconds:
                    time.sleep(0.5)
                    if is_browser_running(port=port):
                        return True
        except Exception:
            pass

    # Standard subprocess launch fallback
    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if is_headless:
        cmd.append("--headless=new")

    if is_container_or_linux:
        for flag in ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
            if flag not in cmd:
                cmd.append(flag)

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        print(f"[DAEMON] Failed to spawn browser: {exc}", file=sys.stderr)
        return False

    start = time.time()
    while time.time() - start < max_wait_seconds:
        time.sleep(0.5)
        if is_browser_running(port=port):
            return True

    return False


if __name__ == "__main__":
    if ensure_browser_running():
        print("[DAEMON] Browser CDP automation session is ONLINE on port 9444.")
        sys.exit(0)
    else:
        print("[DAEMON] Failed to start browser CDP session.", file=sys.stderr)
        sys.exit(1)
