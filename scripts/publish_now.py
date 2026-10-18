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
import json
import urllib.request
from typing import Any

try:
    from scripts import settings, ledger, notify_webhook
except ImportError:
    import settings
    import ledger
    import notify_webhook

from adapters.base import PublishPayload, PublishResult


def check_connectivity(probe_url: str = "https://www.google.com/generate_204", timeout: float = 3.0) -> bool:
    """Probes internet connectivity via lightweight 204 endpoint."""
    try:
        req = urllib.request.Request(probe_url, headers={"User-Agent": "OmniPost/2.5"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--text", default=None, help="Text content to publish (uniform text across platforms)")
    parser.add_argument("--draft", default=None, help="Path to draft JSON or JSON string with platform-native texts")
    parser.add_argument("--slot", help="Specific time slot to publish from daily draft (e.g. 13:00)")
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

        # Check for daily schedule slots structure
        if "slots" in draft_data and isinstance(draft_data["slots"], list) and len(draft_data["slots"]) > 0:
            selected = None
            if getattr(args, "slot", None):
                target_slot = args.slot.strip()
                selected = next((s for s in draft_data["slots"] if s.get("slot") == target_slot), None)
                if not selected:
                    available = [s.get("slot") for s in draft_data["slots"] if s.get("slot")]
                    print(f"[ERROR] Slot '{args.slot}' not found in draft file. Available: {available}", flush=True)
                    return 1
            else:
                # Default to first unposted slot, or slots[0]
                selected = next((s for s in draft_data["slots"] if not s.get("posted", False)), draft_data["slots"][0])
            draft_data = selected

        # Extract platform tailored texts and media
        platforms_dict = draft_data.get("platforms") if isinstance(draft_data.get("platforms"), dict) else {}
        for plat in ["x", "bluesky", "linkedin", "threads"]:
            p_val = draft_data.get(plat)
            if p_val is None and plat in platforms_dict:
                p_val = platforms_dict[plat]

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

    uniform_text = (args.text or "").strip()
    if not uniform_text and draft_data.get("text"):
        uniform_text = str(draft_data["text"]).strip()

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
    elif draft_data.get("image"):
        p = Path(draft_data["image"])
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
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

    start_time = datetime.now()

    if args.dry_run:
        for adapter in adapters:
            p_name = adapter.platform_name.upper()
            plat_key = adapter.platform_name.lower()
            caps = adapter.capabilities
            if plat_key in ("x", "linkedin", "threads"):
                from scripts import browser
                if not browser.alive():
                    status = {"ok": False, "handle": getattr(adapter, "_handle", None) or "Not Running", "error": "Browser CDP daemon not active on port 9444"}
                else:
                    status = adapter.check_session()
            else:
                status = adapter.check_session()

            t_content = tailored_texts.get(plat_key, uniform_text)
            print(f"[{p_name}] Session: {'OK' if status.get('ok') else 'FAIL'}", flush=True)
            print(f"  Account: {status.get('handle')}", flush=True)
            print(f"  Fits limit: {len(t_content) <= caps.max_characters} ({len(t_content)}/{caps.max_characters}c)", flush=True)
            print(f"  Preview: {t_content[:80]}...", flush=True)
            print(f"  Ready to post: {status.get('ok')}\n", flush=True)
        return 0

    if not check_connectivity(timeout=3.0):
        print("[WARN] Internet connection unreachable. Deferring publishing.", flush=True)
        return 0

    st = ledger.load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    slot = draft_data.get("slot") or datetime.now().strftime("%H:%M")

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
            err_msg = "network_timeout"
            print(f"[{p_name}] TIMEOUT ALERT: Operation timed out after {args.timeout}s! Skipping to next platform.", flush=True)
            err_res = PublishResult(platform=plat_key, success=False, error=err_msg)
            results[plat_key] = err_res
            ledger.record_platform_status(
                st, today, slot, plat_key, err_res, text=post_text, kind="manual_test"
            )
            notify_webhook.dispatch_webhook(
                "warning",
                f"⚠️ [{p_name}] Network Timeout Alert",
                f"Post attempt to {p_name} timed out due to unstable network after {args.timeout}s. Check your feed before retrying.",
                {"platform": p_name, "status": "network_timeout", "timeout": str(args.timeout)},
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

    if not args.dry_run and results:
        handles = {}
        for adapter in adapters:
            plat_k = adapter.platform_name.lower()
            try:
                stat = adapter.check_session()
                if stat.get("handle"):
                    handles[plat_k] = stat.get("handle")
            except Exception:
                pass
        total_time = (datetime.now() - start_time).total_seconds()
        notify_webhook.dispatch_summary_card(
            results=results,
            slot=f"{today} {slot}",
            total_time=total_time,
            handles=handles,
        )

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

