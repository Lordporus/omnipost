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

import concurrent.futures

try:
    from scripts import settings, ledger, notify_webhook
except ImportError:
    import settings
    import ledger
    import notify_webhook

from adapters.base import PublishPayload, PublishResult


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--text", default=None, help="Text content to publish (uniform text across platforms)")
    parser.add_argument("--draft", default=None, help="Path to draft JSON or JSON string with platform-native texts")
    parser.add_argument("--dry-run", action="store_true", help="Simulate publish without sending")
    parser.add_argument("--image", help="Optional local image path to attach")
    parser.add_argument("--platforms", help="Comma-separated platforms to target (e.g. linkedin,threads)")
    parser.add_argument("--timeout", type=float, default=45.0, help="Per-platform timeout in seconds (default: 45)")
    args = parser.parse_args()

    draft_data: dict[str, Any] = {}
    tailored_texts: dict[str, str] = {}
    tailored_media: dict[str, list[Path]] = {}

    if args.draft:
        draft_str = args.draft.strip()
        p = Path(draft_str)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
            try:
                draft_data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[ERROR] Failed to read draft file {p}: {exc}", flush=True)
                return 1
        else:
            try:
                draft_data = json.loads(draft_str)
            except Exception:
                print(f"[ERROR] Specified draft path does not exist and is not valid JSON: {args.draft}", flush=True)
                return 1

        # Extract platform tailored texts and media
        platforms_dict = draft_data.get("platforms") if isinstance(draft_data.get("platforms"), dict) else {}
        for plat in ["x", "bluesky", "linkedin", "threads"]:
            p_val = draft_data.get(plat)
            if isinstance(p_val, dict):
                if p_val.get("text"):
                    tailored_texts[plat] = str(p_val["text"])
                if p_val.get("media") and isinstance(p_val["media"], list):
                    paths = []
                    for m in p_val["media"]:
                        mp = Path(m) if Path(m).is_absolute() else (ROOT / m)
                        if mp.exists():
                            paths.append(mp)
                    if paths:
                        tailored_media[plat] = paths
            elif isinstance(p_val, str) and p_val.strip():
                tailored_texts[plat] = p_val.strip()
            elif plat in platforms_dict and isinstance(platforms_dict[plat], str):
                tailored_texts[plat] = platforms_dict[plat].strip()

    uniform_text = (args.text or "").strip()
    if not uniform_text and not tailored_texts:
        print("[ERROR] Post text or valid --draft must be provided.", flush=True)
        return 1

    media_paths = []
    if args.image:
        p = Path(args.image)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print(f"[ERROR] Specified image not found: {p}", flush=True)
            return 1
        media_paths.append(p)

    adapters = settings.get_active_adapters()
    if args.platforms:
        target_set = {p.strip().lower() for p in args.platforms.split(",") if p.strip()}
        adapters = [a for a in adapters if a.platform_name.lower() in target_set]

    if not adapters:
        print("[ERROR] No active publishing adapters selected.", flush=True)
        return 1

    print("==================================================", flush=True)
    print("OmniPost - Multi-Platform Single Publisher", flush=True)
    print("==================================================", flush=True)
    if uniform_text:
        print(f"Content: {uniform_text}", flush=True)
        print(f"Length:  {len(uniform_text)} characters", flush=True)
    if tailored_texts:
        print(f"Native Drafts: {list(tailored_texts.keys())}", flush=True)
    print(f"Target:  {[a.platform_name.upper() for a in adapters]}", flush=True)
    print(f"Timeout: {args.timeout}s per platform", flush=True)
    if args.dry_run:
        print("Mode:    DRY-RUN (No real posts will be made)", flush=True)
    print("==================================================\n", flush=True)

    if args.dry_run:
        for adapter in adapters:
            p_name = adapter.platform_name.upper()
            plat_key = adapter.platform_name.lower()
            caps = adapter.capabilities
            status = adapter.check_session()
            t_content = tailored_texts.get(plat_key, uniform_text)
            print(f"[{p_name}] Session: {'OK' if status.get('ok') else 'FAIL'}", flush=True)
            print(f"  Account: {status.get('handle')}", flush=True)
            print(f"  Fits limit: {len(t_content) <= caps.max_characters} ({len(t_content)}/{caps.max_characters}c)", flush=True)
            print(f"  Preview: {t_content[:80]}...", flush=True)
            print(f"  Ready to post: {status.get('ok')}\n", flush=True)
        return 0

    st = ledger.load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    slot = datetime.now().strftime("%H:%M")

    results: dict[str, PublishResult] = {}
    for adapter in adapters:
        p_name = adapter.platform_name.upper()
        plat_key = adapter.platform_name.lower()
        caps = adapter.capabilities

        post_text = tailored_texts.get(plat_key, uniform_text)
        if len(post_text) > caps.max_characters:
            print(f"[{p_name}] Text exceeds limit ({caps.max_characters}c). Trimming.", flush=True)
            post_text = post_text[: caps.max_characters - 3].rstrip() + "..."

        plat_media = list(media_paths)
        if plat_key in tailored_media:
            plat_media = tailored_media[plat_key]

        payload = PublishPayload(
            text=post_text,
            media_paths=plat_media,
            extra_metadata={"kind": "manual_test"},
        )

        print(f"[{p_name}] Publishing (max {args.timeout}s)...", flush=True)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(adapter.publish, payload)
                res = future.result(timeout=args.timeout)

            results[plat_key] = res
            ledger.record_platform_status(
                st, today, slot, plat_key, res, text=post_text, kind="manual_test"
            )
            if res.success:
                print(f"[{p_name}] SUCCESS!", flush=True)
                print(f"  URL:      {res.url or 'N/A'}", flush=True)
                print(f"  Verified: {res.verified}", flush=True)
            else:
                print(f"[{p_name}] FAILED: {res.error}", flush=True)
                notify_webhook.dispatch_webhook(
                    "failure",
                    f"[{p_name}] Publishing Failed",
                    res.error or "Unknown failure",
                    {"platform": p_name, "error": str(res.error)},
                )
        except concurrent.futures.TimeoutError:
            err_msg = f"Operation timed out after {args.timeout}s"
            print(f"[{p_name}] TIMEOUT ALERT: {err_msg}! Skipping to next platform.", flush=True)
            err_res = PublishResult(platform=plat_key, success=False, error=err_msg)
            results[plat_key] = err_res
            ledger.record_platform_status(
                st, today, slot, plat_key, err_res, text=post_text, kind="manual_test"
            )
            notify_webhook.dispatch_webhook(
                "failure",
                f"[{p_name}] Publishing Timed Out",
                f"Publishing to {p_name} timed out after {args.timeout} seconds.",
                {"platform": p_name, "timeout_seconds": str(args.timeout)},
            )
        except Exception as exc:
            print(f"[{p_name}] EXCEPTION: {exc}", flush=True)
            err_res = PublishResult(platform=plat_key, success=False, error=str(exc))
            results[plat_key] = err_res
            ledger.record_platform_status(
                st, today, slot, plat_key, err_res, text=post_text, kind="manual_test"
            )
            notify_webhook.dispatch_webhook(
                "failure",
                f"[{p_name}] Publishing Exception",
                str(exc),
                {"platform": p_name, "exception": str(exc)},
            )

        print("-" * 50, flush=True)

    print("\n================== Summary ==================", flush=True)
    all_ok = all(r.success for r in results.values())
    for plat, r in results.items():
        status_sym = "[PASS]" if r.success else "[FAIL]"
        print(f"{status_sym} {plat.upper()}: url={r.url} verified={r.verified} error={r.error}", flush=True)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

