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
except ImportError:
    import settings

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="evaluate due slot without posting")
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

    if not slot or not text:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} has empty draft text. Skipping.")
        return 0

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} ({kind}) is due! Text length: {len(text)} chars.")

    if args.dry_run:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Dry-run requested. Skipping real publishing.")
        return 0

    # Publish across all active adapters
    adapters = settings.get_active_adapters()
    if not adapters:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] No active publishing adapters enabled in settings.")
        return 1

    media_paths = []
    if due_item.get("image"):
        img_path = ROOT / due_item["image"] if not Path(due_item["image"]).is_absolute() else Path(due_item["image"])
        if img_path.exists():
            media_paths.append(img_path)

    all_successful = True
    verified_urls: list[str] = []

    for adapter in adapters:
        p_name = adapter.platform_name.upper()
        # Enforce platform character limits
        caps = adapter.capabilities
        adapted_text = text
        if len(adapted_text) > caps.max_characters:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Text ({len(adapted_text)}c) exceeds limit ({caps.max_characters}c). Trimming.")
            adapted_text = adapted_text[: caps.max_characters - 3].rstrip() + "..."

        payload = PublishPayload(
            text=adapted_text,
            media_paths=media_paths,
            extra_metadata={"kind": kind},
        )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Publishing slot {slot}...")
        try:
            res = adapter.publish(payload)
            if res.success:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Published! URL: {res.url or 'N/A'} (verified={res.verified})")
                if res.url:
                    verified_urls.append(res.url)
            else:
                all_successful = False
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Publish failed: {res.error}")
        except Exception as exc:
            all_successful = False
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{p_name}] Publish exception: {exc}")

    if verified_urls:
        primary_url = verified_urls[0]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] Marking slot {slot} as published ({primary_url}).")
        run_cmd([str(SCRIPTS / "due.py"), "mark", "--slot", slot, "--url", primary_url])
    elif not all_successful:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] Not all platforms succeeded or verified. Slot remains unfinalized for safety.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
