#!/usr/bin/env python
"""Prerequisite & Diagnostic Checker + State File Guard.

Validates that system prerequisites, ports, filesystem permissions,
and state file guarantees are met for OmniPost.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import settings
except ImportError:
    from scripts import settings


def guarantee_state_files(root: Path | None = None) -> None:
    """Ensures state.json and .env exist as regular files (not directories).

    - If state.json or .env is a directory, raises ValueError.
    - If state.json missing, writes '{}'.
    - If .env missing, writes empty file.
    - Ensures drafts/, swipe/, scratch/ directories exist.
    """
    base = root if root is not None else ROOT

    state_path = base / "state.json"
    if state_path.is_dir():
        raise ValueError(f"{state_path.name} is a directory, expected regular file")
    if not state_path.exists():
        state_path.write_text("{}", encoding="utf-8")

    env_path = base / ".env"
    if env_path.is_dir():
        raise ValueError(f"{env_path.name} is a directory, expected regular file")
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")

    for dir_name in ("drafts", "swipe", "scratch"):
        (base / dir_name).mkdir(parents=True, exist_ok=True)


def check_prerequisites(root: Path | None = None) -> dict[str, Any]:
    """Runs system diagnostics:

    - python: sys.version_info >= (3, 10)
    - git: shutil.which('git') is not None
    - browser: checks settings.find_chrome() or ['msedge', 'google-chrome', 'chromium-browser', 'chromium']
    - docker: checks shutil.which('docker') and shutil.which('docker-compose') or 'docker compose'
    - port_9444: socket bind test on 127.0.0.1:9444
    - ledger_writable: atomic write & delete of .write_test.tmp
    - state_files_guaranteed: calls guarantee_state_files()
    """
    base = root if root is not None else ROOT
    diagnostics: dict[str, Any] = {}

    # 1. Python Check
    py_ok = sys.version_info >= (3, 10)
    py_ver = f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    diagnostics["python"] = {"ok": py_ok, "version": py_ver}

    # 2. Git Check
    git_bin = shutil.which("git")
    if git_bin:
        git_ver = ""
        try:
            res = subprocess.run([git_bin, "--version"], capture_output=True, text=True, timeout=3)
            git_ver = res.stdout.strip()
        except Exception:
            git_ver = "git installed"
        diagnostics["git"] = {"ok": True, "version": git_ver}
    else:
        diagnostics["git"] = {"ok": False, "version": ""}

    # 3. Browser Check
    browser_path = ""
    browser_ok = False
    try:
        cfg = settings.load() if hasattr(settings, "load") else {}
        explicit = (cfg.get("browser") or {}).get("chrome_path") or ""
        found = settings.find_chrome(explicit) if hasattr(settings, "find_chrome") else None
        if found:
            browser_path = str(found)
            browser_ok = True
    except Exception:
        pass

    if not browser_ok:
        for b in ("msedge", "google-chrome", "chromium-browser", "chromium"):
            w = shutil.which(b)
            if w:
                browser_path = str(w)
                browser_ok = True
                break

    diagnostics["browser"] = {"ok": browser_ok, "path": browser_path}

    # 4. Docker Check
    docker_bin = shutil.which("docker")
    compose_bin = shutil.which("docker-compose")
    compose_ok = bool(compose_bin)
    if docker_bin and not compose_ok:
        try:
            c_res = subprocess.run([docker_bin, "compose", "version"], capture_output=True, text=True, timeout=3)
            if c_res.returncode == 0:
                compose_ok = True
        except Exception:
            pass
    diagnostics["docker"] = {"ok": bool(docker_bin), "compose": compose_ok}

    # 5. Port 9444 Check
    port_available = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 9444))
            port_available = True
    except OSError:
        port_available = False
    diagnostics["port_9444"] = {"available": port_available}

    # 6. Ledger Writable Check
    ledger_ok = False
    test_file = base / ".write_test.tmp"
    try:
        with test_file.open("w", encoding="utf-8") as f:
            f.write("write_test")
        if test_file.exists():
            test_file.unlink()
            ledger_ok = True
    except Exception:
        ledger_ok = False
    finally:
        if test_file.exists():
            try:
                test_file.unlink()
            except Exception:
                pass
    diagnostics["ledger_writable"] = {"ok": ledger_ok}

    # 7. State Files Guaranteed Check
    state_ok = False
    try:
        guarantee_state_files(base)
        state_ok = True
    except Exception:
        state_ok = False
    diagnostics["state_files_guaranteed"] = {"ok": state_ok}

    return diagnostics


def main() -> None:
    results = check_prerequisites()
    print(json.dumps(results, indent=2))
    all_ok = (
        results["python"]["ok"]
        and results["browser"]["ok"]
        and results["ledger_writable"]["ok"]
        and results["state_files_guaranteed"]["ok"]
    )
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
