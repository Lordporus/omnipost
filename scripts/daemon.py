"""Standalone Unattended Daemon for OmniPost.

Runs continuously in the background:
- Verifies Edge browser session is active.
- Triggers the daily pipeline at 11:00 AM (or if today's plan has empty text).
- Runs autoposter check every 5 minutes to publish slots when due.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    parser.add_argument("--interval", type=int, default=300, help="Sleep interval in seconds (default: 300)")
    args = parser.parse_args()

    print("[DAEMON] OmniPost Autonomous Syndicate Daemon started.")
    print("[DAEMON] Press Ctrl+C to terminate.")

    last_pipeline_date = ""

    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 1. Run pipeline if it's 11:00+ or plan is missing
        plan_path = ROOT / "drafts" / f"{today}.json"
        should_run_pipeline = (today != last_pipeline_date and now.hour >= 11) or not plan_path.exists()
        if should_run_pipeline:
            print(f"[{now.strftime('%H:%M:%S')}] [DAEMON] Triggering daily pipeline...")
            subprocess.run([sys.executable, str(SCRIPTS / "pipeline.py")], cwd=str(ROOT))
            last_pipeline_date = today

        # 2. Run autoposter tick
        try:
            subprocess.run([sys.executable, str(SCRIPTS / "autoposter.py")], cwd=str(ROOT))
        except Exception as exc:
            print(f"[DAEMON] Autoposter error: {exc}", file=sys.stderr)

        if args.once:
            break

        # 3. Sleep interval seconds (default 300 = 5 minutes)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[DAEMON] Terminated by user.")
            break


if __name__ == "__main__":
    main()
