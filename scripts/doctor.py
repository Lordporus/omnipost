#!/usr/bin/env python
"""Readiness check - run this first, and after anything breaks.

Tells you exactly which parts of the pipeline can run right now, what is
missing, and the one command that fixes each gap. Nothing here changes state or
posts anything.

  python doctor.py
  python doctor.py --live     # also try the network + the browser session
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import settings  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OK, WARN, BAD = "OK", "WARN", "MISSING"


def check_python() -> tuple[str, str]:
    if sys.version_info < (3, 10):
        return BAD, f"python {sys.version.split()[0]} - needs 3.10+ for zoneinfo and X | Y types"
    return OK, f"python {sys.version.split()[0]}"


def check_deps() -> tuple[str, str]:
    try:
        import websockets  # noqa: F401
        return OK, "websockets installed"
    except ImportError:
        return BAD, "websockets missing - run:  pip install -r requirements.txt"


def check_config() -> tuple[str, str]:
    if not settings.CONFIG_PATH.exists():
        return BAD, f"no config.json - run:  cp {settings.EXAMPLE_PATH.name} config.json"
    c = settings.load()
    platforms = settings.get_platforms(c)
    active = [p for p, data in platforms.items() if data.get("enabled", True)]
    
    parts = []
    if "x" in active:
        x_handle = platforms["x"].get("handle") or c.get("handle") or ""
        lim = settings.limit(c)
        cap = f"{lim['chars']}c" + ("" if lim["verified"] else " (unverified)")
        parts.append(f"x: @{x_handle.lstrip('@') or 'unset'} [{cap}]")
    if "bluesky" in active:
        b_ident = platforms["bluesky"].get("identifier") or "unset"
        parts.append(f"bluesky: @{b_ident}")

    if not parts:
        return WARN, "config.json ok, but no publishing platforms enabled"
    return OK, f"config.json ok - active: {', '.join(parts)}"


def check_chrome() -> tuple[str, str]:
    cfg = settings.load()
    explicit = (cfg.get("browser") or {}).get("chrome_path") or ""
    found = settings.find_chrome(explicit)
    if not found:
        return BAD, ("no Chrome/Chromium/Edge found - install one, or set "
                     "browser.chrome_path in config.json")
    return OK, str(found)


def check_dirs() -> tuple[str, str]:
    made = []
    for name in ("swipe", "drafts", "shots", "scratch"):
        (ROOT / name).mkdir(exist_ok=True)
        made.append(name)
    return OK, "writable: " + ", ".join(made)


def check_live() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        import research
        got = research.hn(points=50, hours=24, limit=3)
        out.append((OK, f"Hacker News reachable ({len(got)} stories in 24h)"))
    except Exception as err:
        out.append((BAD, f"Hacker News unreachable: {type(err).__name__}: {str(err)[:70]}"))

    try:
        import research
        items, status = research.rss(hours=48, per_feed=3)
        good = sum(1 for v in status.values() if v.startswith("ok"))
        bad = [k for k, v in status.items() if not v.startswith("ok")]
        lvl = OK if good else BAD
        extra = f" - failing: {', '.join(bad[:4])}" if bad else ""
        out.append((lvl, f"RSS feeds: {good}/{len(status)} reachable{extra}"))
    except Exception as err:
        out.append((BAD, f"RSS check failed: {type(err).__name__}: {str(err)[:70]}"))

    try:
        import browser
        if not browser.alive():
            browser.ensure_chrome()
        out.append((OK, f"automation browser up on port {browser._port()}"))
    except Exception as err:
        out.append((WARN, f"browser not running: {str(err)[:80]} "
                          f"- it starts on demand, so this is only a problem if it persists"))
        return out

    # Check active platform sessions
    adapters = settings.get_active_adapters()
    for adapter in adapters:
        try:
            sess = adapter.check_session()
            if sess.get("ok"):
                h = sess.get("handle") or "logged in"
                out.append((OK, f"{adapter.platform_name.upper()} session live as @{h}"))
            else:
                out.append((WARN, f"{adapter.platform_name.upper()} session check failed: {sess.get('error', 'not logged in')}"))
        except Exception as err:
            out.append((WARN, f"could not check {adapter.platform_name} session: {str(err)[:80]}"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also test network + browser")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    results = [("python", check_python()), ("dependencies", check_deps()),
               ("config", check_config()), ("chrome", check_chrome()),
               ("directories", check_dirs())]
    if a.live:
        results += [("live", r) for r in check_live()]

    if a.json:
        print(json.dumps([{"check": k, "status": s, "detail": d} for k, (s, d) in results],
                         indent=2))
        return

    icon = {OK: "OK     ", WARN: "WARN   ", BAD: "MISSING"}
    print("\nOmniPost - readiness\n" + "=" * 60)
    worst = OK
    for name, (status, detail) in results:
        print(f"[{icon[status]}] {name:<14} {detail}")
        if status == BAD:
            worst = BAD
        elif status == WARN and worst == OK:
            worst = WARN
    print("=" * 60)
    blocked = sum(1 for _, (s, _) in results if s == BAD)
    if blocked:
        print(f"{blocked} blocking item(s). Fix those, then re-run this.")
    else:
        print("Nothing blocking. Next: python scripts/due.py make-plan, "
              "then have your agent write and fill the drafts.")
    if not a.live:
        print("(network and browser were not tested - re-run with --live)")


if __name__ == "__main__":
    main()
