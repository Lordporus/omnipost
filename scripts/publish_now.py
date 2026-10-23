#!/usr/bin/env python
"""Immediate manual publisher for OmniPost across all active platforms.

Dispatches a single post to all enabled platform adapters (X, Bluesky,
LinkedIn, Threads) with per-platform character limits, idempotency reservations,
killable worker timeouts, and truthful ledger logging.

Exit codes (live):
  0  every target is published_verified
  1  at least one target failed
  2  connectivity is offline / publishing was deferred
  3  every dispatch completed but at least one target is submitted_unverified

Usage:
  python scripts/publish_now.py --text "Hello from OmniPost!"
  python scripts/publish_now.py --text "Hello from OmniPost!" --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

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


def _dispatch_worker(
    adapter: Any,
    payload: PublishPayload,
    timeout: float,
) -> PublishResult:
    """Run one publish in a killable subprocess and reconcile a timeout."""
    platform = adapter.platform_name.lower()
    fd, raw_result_path = tempfile.mkstemp(prefix="omnipost_publish_", suffix=".json")
    os.close(fd)
    result_path = Path(raw_result_path)
    worker_input = {"platform": platform, **payload.to_dict()}

    proc = None
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.publish_worker",
                "--result-file",
                str(result_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(ROOT),
        )
        try:
            stdout, stderr = proc.communicate(
                json.dumps(worker_input, ensure_ascii=False, default=str),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""

            verified = False
            try:
                verified = bool(adapter.verify(None, payload.text[:80]))
            except Exception:
                verified = False

            return PublishResult(
                platform=platform,
                success=True,
                verified=verified,
                error=None if verified else "timeout_unreconciled",
                raw_response={
                    "timeout": True,
                    "reconciled": verified,
                    "stdout": stdout or "",
                    "stderr": stderr or "",
                },
            )

        if proc.returncode != 0:
            error = (stderr or stdout or f"worker_exit_{proc.returncode}").strip()
            return PublishResult(
                platform=platform,
                success=False,
                verified=False,
                error=error,
                raw_response={"returncode": proc.returncode, "stderr": stderr or ""},
            )

        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return PublishResult(
                platform=platform,
                success=False,
                verified=False,
                error=f"invalid_worker_result: {exc}",
                raw_response={"stderr": stderr or ""},
            )

        result = PublishResult.from_dict(data)
        if not result.platform:
            result.platform = platform
        return result
    finally:
        try:
            result_path.unlink(missing_ok=True)
        except OSError:
            pass


def _status_label(status: str | None) -> str:
    if status == ledger.STATUS_PUBLISHED_VERIFIED:
        return "[VERIFIED]"
    if status == ledger.STATUS_SUBMITTED_UNVERIFIED:
        return "[UNVERIFIED]"
    if status == ledger.STATUS_FAILED:
        return "[FAIL]"
    return "[PENDING]"


def _exit_code_for_state(
    state: dict,
    date: str,
    slot: str,
    targets: list[str],
) -> int:
    statuses = [
        (ledger.get_platform_status(state, date, slot, platform) or {}).get("status")
        for platform in targets
    ]
    if statuses and all(status == ledger.STATUS_PUBLISHED_VERIFIED for status in statuses):
        return 0
    if any(status == ledger.STATUS_FAILED for status in statuses):
        return 1
    if any(status == ledger.STATUS_SUBMITTED_UNVERIFIED for status in statuses):
        return 3
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--text", default=None, help="Text content to publish (uniform text across platforms)")
    parser.add_argument("--draft", default=None, help="Path to draft JSON or JSON string with platform-native texts")
    parser.add_argument("--slot", help="Specific time slot to publish from daily draft (e.g. 13:00)")
    parser.add_argument("--fresh", action="store_true", help="Harvest fresh intelligence, generate today's multi-slot draft, and compile unique assets")
    parser.add_argument("--force-fresh", action="store_true", help="Force re-generation of today's draft even if already populated")
    parser.add_argument("--dry-run", action="store_true", help="Simulate publish without sending")
    parser.add_argument("--image", help="Optional local image path to attach")
    parser.add_argument("--platforms", help="Comma-separated platforms to target (e.g. linkedin,threads)")
    parser.add_argument("--timeout", type=float, default=80.0, help="Per-platform timeout in seconds (default: 80)")
    parser.add_argument("--force", action="store_true", help="Override an existing idempotency reservation")
    parser.add_argument("--retry-failed", action="store_true", help="Explicitly retry failed records (never unverified ones)")
    args = parser.parse_args()

    draft_data: dict[str, Any] = {}
    tailored_texts: dict[str, str] = {}
    tailored_media: dict[str, list[Path]] = {}
    tailored_media_types: dict[str, str] = {}
    tailored_metadata: dict[str, dict[str, Any]] = {}

    if args.fresh:
        try:
            from scripts import pipeline
            today_str = datetime.now().strftime("%Y-%m-%d")
            print(f"[*] Running autonomous intelligence pipeline for {today_str}...", flush=True)
            plan_file = pipeline.run_daily_pipeline(date_str=today_str, force=args.force_fresh)
            args.draft = str(plan_file)
        except Exception as exc:
            print(f"[ERROR] Failed to run fresh pipeline: {exc}", file=sys.stderr, flush=True)
            return 1

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
                if p_val.get("media_type"):
                    tailored_media_types[plat] = str(p_val["media_type"]).strip()
                if p_val.get("document_title"):
                    tailored_metadata.setdefault(plat, {})["document_title"] = str(p_val["document_title"]).strip()
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
        print("[DEFERRED] offline: internet connection unreachable; no publish was attempted.", flush=True)
        return 2

    st = ledger.load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    slot = draft_data.get("slot") or datetime.now().strftime("%H:%M")
    targets = [adapter.platform_name.lower() for adapter in adapters]

    results: dict[str, PublishResult] = {}
    for adapter in adapters:
        p_name = adapter.platform_name.upper()
        plat_key = adapter.platform_name.lower()
        caps = adapter.capabilities
        key = f"{today}:{slot}:{plat_key}"

        if not args.force and ledger.is_platform_done(st, today, slot, plat_key):
            print(f"[SKIP] [{p_name}] slot {slot} is already published_verified.", flush=True)
            continue

        existing = ledger.get_idempotency_record(st, key)
        if existing is not None and not args.force:
            existing_status = existing.get("status")
            if not (existing_status == ledger.STATUS_FAILED and args.retry_failed):
                print(
                    f"[SKIP] [{p_name}] slot {slot} already has idempotency state "
                    f"'{existing_status}'.",
                    flush=True,
                )
                continue

        if not ledger.reserve_idempotency(
            key,
            plat_key,
            force=args.force,
            allow_failed=args.retry_failed,
        ):
            print(
                f"[SKIP] [{p_name}] slot {slot} already published/unverified.",
                flush=True,
            )
            continue

        # The reservation is committed in its own transaction; never dispatch on
        # a stale pre-reservation view of state.
        st = ledger.load_state()

        post_text = tailored_texts.get(plat_key, uniform_text)
        if len(post_text) > caps.max_characters:
            print(f"[{p_name}] Text exceeds limit ({caps.max_characters}c). Trimming.", flush=True)
            post_text = post_text[: caps.max_characters - 3].rstrip() + "..."

        plat_media = list(media_paths)
        if plat_key in tailored_media:
            plat_media = tailored_media[plat_key]

        media_type = tailored_media_types.get(plat_key, "image")
        extra_meta = {"kind": "manual_test"}
        if plat_key in tailored_metadata:
            extra_meta.update(tailored_metadata[plat_key])

        payload = PublishPayload(
            text=post_text,
            media_paths=plat_media,
            media_type=media_type,
            extra_metadata=extra_meta,
        )

        print(f"[{p_name}] Publishing (max {args.timeout}s)...", flush=True)
        try:
            res = _dispatch_worker(adapter, payload, args.timeout)
        except Exception as exc:
            res = PublishResult(
                platform=plat_key,
                success=False,
                verified=False,
                error=str(exc),
            )

        results[plat_key] = res
        ledger.record_platform_status(
            st,
            today,
            slot,
            plat_key,
            res,
            text=post_text,
            kind="manual_test",
            idempotency_key=key,
        )

        if res.success and res.verified:
            print(f"[VERIFIED] [{p_name}] live", flush=True)
            print(f"  URL:      {res.url or 'N/A'}", flush=True)
        elif res.success:
            print(f"[UNVERIFIED] [{p_name}] submitted but not read back", flush=True)
            print(f"  Error:    {res.error or 'verification_failed'}", flush=True)
            notify_webhook.dispatch_webhook(
                "warning",
                f"⚠️ [{p_name}] Submitted Unverified",
                f"{p_name} accepted the post but read-back did not verify it. Do not auto-retry.",
                {"platform": p_name, "status": ledger.STATUS_SUBMITTED_UNVERIFIED, "error": res.error},
            )
        else:
            print(f"[FAIL] [{p_name}] {res.error}", flush=True)
            notify_webhook.dispatch_webhook(
                "failure",
                f"[{p_name}] Publishing Failed",
                res.error or "Unknown failure",
                {"platform": p_name, "error": str(res.error)},
            )

        print("-" * 50, flush=True)

    final_state = ledger.load_state()
    print("\n================== Summary ==================", flush=True)
    for plat_key in targets:
        status = (ledger.get_platform_status(final_state, today, slot, plat_key) or {}).get("status")
        record = ledger.get_platform_status(final_state, today, slot, plat_key) or {}
        print(
            f"{_status_label(status)} {plat_key.upper()}: "
            f"url={record.get('url')} verified={record.get('verified')} "
            f"error={record.get('error')}",
            flush=True,
        )

    if results:
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

    return _exit_code_for_state(final_state, today, slot, targets)


if __name__ == "__main__":
    sys.exit(main())
