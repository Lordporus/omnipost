#!/usr/bin/env python
"""Autonomous posting runner for OmniPost.

Orchestrates the unattended schedule execution:
1. Ensures today's daily plan exists (creates jittered slots via due.py make-plan if missing).
2. Checks whether a slot is currently due via due.py check.
3. If a slot is due, publishes the text via post.py post.
4. Verifies published status and marks the slot in the daily plan only upon verification.

Usage:
  python scripts/autoposter.py            # run single check and execute if due
  python scripts/autoposter.py --dry-run  # check without publishing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

try:
    from scripts import settings
    from scripts import ledger
    from scripts import pipeline
    from scripts import notify
    from scripts.publish_now import _dispatch_worker
except ImportError:
    import settings
    import ledger
    import pipeline
    import notify
    from publish_now import _dispatch_worker

from adapters.base import PublishPayload



def run_cmd(args: list[str]) -> tuple[int, str]:
    res = subprocess.run(
        [sys.executable, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    return res.returncode, res.stdout.strip()


def ensure_daily_plan() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    plan_file = ROOT / "drafts" / f"{today}.json"
    if not plan_file.exists():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [PLAN] Generating daily plan for {today} with random jitter...")
        run_cmd([str(SCRIPTS / "due.py"), "make-plan"])


def _retry_failed_enabled() -> bool:
    """Failed records are retried only when the operator opts in."""
    try:
        cfg = settings.load()
    except Exception:
        return False
    publish_cfg = cfg.get("publish", {})
    if not isinstance(publish_cfg, dict):
        return False
    return bool(publish_cfg.get("retry_failed", False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="evaluate due slot without posting")
    parser.add_argument("--live", action="store_true", help="override config.json dry_run for this run")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-platform publish timeout in seconds (default: 120)")
    args = parser.parse_args()

    ensure_daily_plan()

    # Check what is due right now
    code, out = run_cmd([str(SCRIPTS / "due.py"), "check"])
    if code != 0 or not out or out == "IDLE":
        print(f"[{datetime.now().strftime('%H:%M:%S')}] IDLE - no slot due right now.")
        return 0

    try:
        due_item = json.loads(out)
    except Exception as err:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Non-JSON due output ({err}): {out}")
        return 0

    slot = due_item.get("slot")
    kind = due_item.get("kind", "value")
    text = due_item.get("text")

    if slot and not text:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} has empty draft text. Triggering daily pipeline...")
        try:
            target_date = due_item.get("date") or datetime.now().strftime("%Y-%m-%d")
            pipeline.run_daily_pipeline(target_date)
            code, out = run_cmd([str(SCRIPTS / "due.py"), "check"])
            if code == 0 and out and out != "IDLE":
                due_item = json.loads(out)
                slot = due_item.get("slot")
                kind = due_item.get("kind", kind)
                text = due_item.get("text")
        except Exception as exc:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Pipeline generation failed: {exc}", file=sys.stderr)

    if not slot or not text:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} has empty draft text. Skipping.")
        return 0

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} ({kind}) is due! Text length: {len(text)} chars.")

    try:
        configured_dry_run = bool(settings.load().get("dry_run", False))
    except Exception:
        configured_dry_run = True

    if args.dry_run or (configured_dry_run and not args.live):
        source = "requested" if args.dry_run else "config.json dry_run=true"
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Dry-run ({source}). "
            "Skipping real publishing."
        )
        return 0

    # Publish across all active adapters
    adapters = settings.get_active_adapters()
    if not adapters:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] No active publishing adapters enabled in settings.")
        return 1

    st = ledger.load_state()
    date = due_item.get("date") or datetime.now().strftime("%Y-%m-%d")
    poly_platforms = due_item.get("platforms", {})
    retry_failed = _retry_failed_enabled()
    all_successful = True
    verified_urls: list[str] = []

    # Determine targeted platforms
    target_platforms: list[str] = []
    for adapter in adapters:
        plat_key = adapter.platform_name.lower()
        plat_draft = poly_platforms.get(plat_key, {})
        if poly_platforms and plat_key in poly_platforms and not plat_draft.get("enabled", True):
            continue
        target_platforms.append(plat_key)

    publish_results: dict[str, dict] = {}

    for adapter in adapters:
        plat_key = adapter.platform_name.lower()
        p_name = adapter.platform_name.upper()

        # Check if platform is targeted for this slot
        if plat_key not in target_platforms:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Platform disabled in draft slot. Skipping.")
            continue

        # Check if platform was already successfully published and verified in ledger
        if ledger.is_platform_done(st, date, slot, plat_key):
            done_info = ledger.get_platform_status(st, date, slot, plat_key) or {}
            done_url = done_info.get("url") or "verified"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [SKIP] [{p_name}] Slot {slot} already published ({done_url}). Skipping to prevent duplicates.")
            if done_info.get("url"):
                verified_urls.append(done_info["url"])
            continue

        key = f"{date}:{slot}:{plat_key}"
        existing = ledger.get_idempotency_record(st, key)
        if existing is not None:
            existing_status = existing.get("status")
            if not (existing_status == ledger.STATUS_FAILED and retry_failed):
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] [SKIP] [{p_name}] "
                    f"Slot {slot} already has idempotency state '{existing_status}'. "
                    "Unverified submissions are never auto-retried."
                )
                continue

        if not ledger.reserve_idempotency(
            key,
            plat_key,
            allow_failed=retry_failed,
        ):
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] [SKIP] [{p_name}] "
                f"Slot {slot} was reserved by another publisher. Skipping."
            )
            continue

        # Never dispatch on a stale pre-reservation view of state.
        st = ledger.load_state()

        # Check polymorphic platform configuration
        plat_draft = poly_platforms.get(plat_key, {})
        if poly_platforms and plat_key in poly_platforms:
            adapted_text = plat_draft.get("text") or text
            media_list = plat_draft.get("media") or (due_item.get("image") and [due_item.get("image")]) or []
            media_type = plat_draft.get("media_type", "image")
        else:
            adapted_text = text
            media_list = [due_item["image"]] if due_item.get("image") else []
            media_type = "image"

        # Resolve media paths
        resolved_media: list[Path] = []
        for m in media_list:
            clean_m = Path(str(m).replace("\\", "/"))
            mp = ROOT / clean_m if not clean_m.is_absolute() else clean_m
            if mp.exists():
                resolved_media.append(mp)
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] [WARN] Media path not found: {mp}", file=sys.stderr)

        # Enforce platform character limits
        caps = adapter.capabilities
        if len(adapted_text) > caps.max_characters:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Text ({len(adapted_text)}c) exceeds limit ({caps.max_characters}c). Trimming.")
            adapted_text = adapted_text[: caps.max_characters - 3].rstrip() + "..."

        payload = PublishPayload(
            text=adapted_text,
            media_paths=resolved_media,
            media_type=media_type,
            extra_metadata={
                "kind": kind,
                "document_title": plat_draft.get("document_title") or due_item.get("headline", ""),
            },
        )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Publishing slot {slot}...")
        try:
            # Killable worker: a hung browser call must not stall the daemon.
            res = _dispatch_worker(adapter, payload, args.timeout)
            ledger.record_platform_status(
                st,
                date,
                slot,
                plat_key,
                res,
                text=adapted_text,
                kind=kind,
                idempotency_key=key,
            )
            publish_results[plat_key] = {
                "success": res.success,
                "verified": res.verified,
                "url": res.url,
                "error": res.error,
            }
            if res.success and res.verified:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] [VERIFIED] URL: {res.url or 'N/A'}")
                if res.url:
                    verified_urls.append(res.url)
            elif res.success:
                all_successful = False
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] "
                    f"[UNVERIFIED] submitted but not read back: {res.error or 'verification_failed'}"
                )
            else:
                all_successful = False
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] [FAIL] {res.error}")
        except Exception as exc:
            all_successful = False
            ledger.record_platform_status(
                st,
                date,
                slot,
                plat_key,
                {"success": False, "verified": False, "error": str(exc)},
                text=adapted_text,
                kind=kind,
                idempotency_key=key,
            )
            publish_results[plat_key] = {"success": False, "verified": False, "error": str(exc)}
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Publish exception: {exc}")

    if publish_results:
        try:
            notify.notify_publish(slot, publish_results)
        except Exception as notify_err:
            print(f"[NOTIFY] Warning: Could not dispatch notification: {notify_err}", file=sys.stderr)

    slot_fully_done = ledger.is_slot_fully_published(st, date, slot, target_platforms)
    if slot_fully_done:
        primary_url = verified_urls[0] if verified_urls else "https://omnipost.local"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] Marking slot {slot} as fully published ({primary_url}).")
        run_cmd([str(SCRIPTS / "due.py"), "mark", "--slot", slot, "--url", primary_url])
        return 0
    else:
        pending = ledger.get_pending_platforms(st, date, slot, target_platforms)
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] [PARTIAL] Slot {slot} is not fully verified. "
            f"Remaining channels {pending} require reconciliation or explicit retry."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
