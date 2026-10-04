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

    # Save draft text to scratch buffer
    tmp_text = ROOT / "scratch" / f"due_{slot.replace(':', '')}.txt"
    tmp_text.parent.mkdir(exist_ok=True)
    tmp_text.write_text(text, encoding="utf-8")

    post_args = [str(SCRIPTS / "post.py"), "post", "--text-file", str(tmp_text)]
    if kind == "ai_update":
        post_args.extend(["--kind", "ai_update"])
    if due_item.get("image"):
        img_path = ROOT / due_item["image"] if not Path(due_item["image"]).is_absolute() else Path(due_item["image"])
        if img_path.exists():
            post_args.extend(["--image", str(img_path)])

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Publishing slot {slot}...")
    pcode, pout = run_cmd(post_args)
    if pcode != 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Post command failed (exit code {pcode}): {pout}")
        # Guardrail: Never mark a failed slot as posted
        return 1

    print(f"Publish output: {pout}")

    # Check post verification results
    tweet_url = None
    try:
        post_res = json.loads(pout)
        if post_res.get("verified") and post_res.get("tweet_url"):
            tweet_url = post_res["tweet_url"]
    except Exception:
        pass

    # If post.py did not confirm immediately, do a fallback profile read-back
    if not tweet_url:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling profile read-back verification...")
        vcode, vout = run_cmd([str(SCRIPTS / "post.py"), "verify"])
        try:
            posts = json.loads(vout)
            head = text[:40].replace("\n", " ").strip().lower()
            matched = next((p for p in posts if head in p.get("text", "").replace("\n", " ").lower()), None)
            if matched and matched.get("url"):
                tweet_url = matched["url"]
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Verification parsing error: {e}")

    if tweet_url:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] Post verified live at: {tweet_url}")
        run_cmd([str(SCRIPTS / "due.py"), "mark", "--slot", slot, "--url", tweet_url])
        run_cmd([str(SCRIPTS / "post.py"), "shot", "--what", "profile"])
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] Post sent but exact match not immediately verified on profile timeline.")
        print("Leaving slot unmarked for safety retry or manual review.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
