#!/usr/bin/env python
"""Immediate manual publisher for OmniPost across all active platforms.

Dispatches a single post to all enabled platform adapters (X, Bluesky,
LinkedIn, Threads) with per-platform character limits and atomic ledger logging.

Usage:
  python scripts/publish_now.py --text "Hello from OmniPost!"
  python scripts/publish_now.py --text "Hello from OmniPost!" --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from scripts import settings, ledger
except ImportError:
    import settings
    import ledger

from adapters.base import PublishPayload, PublishResult


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--text", required=True, help="Text content to publish")
    parser.add_argument("--dry-run", action="store_true", help="Simulate publish without sending")
    parser.add_argument("--image", help="Optional local image path to attach")
    parser.add_argument("--platforms", help="Comma-separated platforms to target (e.g. linkedin,threads)")
    args = parser.parse_args()

    text = args.text.strip()
    if not text:
        print("[ERROR] Post text cannot be empty.")
        return 1

    media_paths = []
    if args.image:
        p = Path(args.image)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print(f"[ERROR] Specified image not found: {p}")
            return 1
        media_paths.append(p)

    adapters = settings.get_active_adapters()
    if args.platforms:
        target_set = {p.strip().lower() for p in args.platforms.split(",") if p.strip()}
        adapters = [a for a in adapters if a.platform_name.lower() in target_set]

    if not adapters:
        print("[ERROR] No active publishing adapters selected.")
        return 1

    print("==================================================")
    print("OmniPost - Multi-Platform Single Publisher")
    print("==================================================")
    print(f"Content: {text}")
    print(f"Length:  {len(text)} characters")
    print(f"Target:  {[a.platform_name.upper() for a in adapters]}")
    if args.dry_run:
        print("Mode:    DRY-RUN (No real posts will be made)")
    print("==================================================\n")

    if args.dry_run:
        for adapter in adapters:
            p_name = adapter.platform_name.upper()
            caps = adapter.capabilities
            status = adapter.check_session()
            print(f"[{p_name}] Session: {'OK' if status.get('ok') else 'FAIL'}")
            print(f"  Account: {status.get('handle')}")
            print(f"  Fits limit: {len(text) <= caps.max_characters} ({len(text)}/{caps.max_characters}c)")
            print(f"  Ready to post: {status.get('ok')}\n")
        return 0

    st = ledger.load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    slot = datetime.now().strftime("%H:%M")

    results: dict[str, PublishResult] = {}
    for adapter in adapters:
        p_name = adapter.platform_name.upper()
        plat_key = adapter.platform_name.lower()
        caps = adapter.capabilities

        post_text = text
        if len(post_text) > caps.max_characters:
            print(f"[{p_name}] Text exceeds limit ({caps.max_characters}c). Trimming.")
            post_text = post_text[: caps.max_characters - 3].rstrip() + "..."

        payload = PublishPayload(
            text=post_text,
            media_paths=media_paths,
            extra_metadata={"kind": "manual_test"},
        )

        print(f"[{p_name}] Publishing...")
        try:
            res = adapter.publish(payload)
            results[plat_key] = res
            ledger.record_platform_status(
                st, today, slot, plat_key, res, text=post_text, kind="manual_test"
            )
            if res.success:
                print(f"[{p_name}] SUCCESS!")
                print(f"  URL:      {res.url or 'N/A'}")
                print(f"  Verified: {res.verified}")
            else:
                print(f"[{p_name}] FAILED: {res.error}")
        except Exception as exc:
            print(f"[{p_name}] EXCEPTION: {exc}")
            err_res = PublishResult(platform=plat_key, success=False, error=str(exc))
            results[plat_key] = err_res
            ledger.record_platform_status(
                st, today, slot, plat_key, err_res, text=post_text, kind="manual_test"
            )

        print("-" * 50)

    print("\n================== Summary ==================")
    all_ok = all(r.success for r in results.values())
    for plat, r in results.items():
        status_sym = "[PASS]" if r.success else "[FAIL]"
        print(f"{status_sym} {plat.upper()}: url={r.url} verified={r.verified} error={r.error}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
