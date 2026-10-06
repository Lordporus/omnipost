#!/usr/bin/env python
"""Zero-Cost Schedule Gate for OmniPost.

Used by cron monitors, systemd timers, or task schedulers to evaluate whether
a post is due without spinning up heavy browser or LLM agent instances.

Stdout Contract:
  * IDLE\\n (byte-identical) -> exit 0. Nothing is due right now.
                                Cron monitor suppresses agent invocation ($0 cost).
  * JSON string -> exit 0.      A post slot is due. The JSON contains the slot,
                                polymorphic draft copy, and monotonic tick counter.
  * Stderr / exit 1 ->           An actionable error occurred.

Usage:
  python scripts/gate.py                # check schedule -> IDLE or JSON
  python scripts/gate.py --wake         # check schedule -> formatted agent prompt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import due
    import settings
except ImportError:
    from scripts import due, settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def check_gate(wake: bool = False) -> int:
    """Evaluates whether any slot is due. Emits byte-identical IDLE or due payload."""
    try:
        draft = due.due()
    except Exception as exc:
        sys.stderr.write(f"gate error: {exc}\n")
        return 1

    if not draft:
        # Byte-identical suppression output: cron monitor checks for this exact string
        sys.stdout.write("IDLE\n")
        sys.stdout.flush()
        return 0

    draft["tick"] = due.tick()

    if not wake:
        sys.stdout.write(json.dumps(draft, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return 0

    # Format human / agent wake block
    kind = draft.get("kind", "value")
    handle_str = draft.get("handle") or settings.load().get("handle") or "your account"
    slot = draft.get("slot")
    due_at = draft.get("due_at")
    mins_late = draft.get("minutes_late", 0)
    text = draft.get("text", "")

    msg = f"""A post is DUE for @{handle_str}.

  slot       {slot}  ({kind}, {mins_late} min late)
  due at     {due_at}

Draft text (publish VERBATIM - do not edit, do not add hashtags or emoji):
---8<---
{text}
---8<---

Execute publishing pipeline:
  python scripts/post.py check
  python scripts/publish_now.py --slot {slot}
"""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

    # Cache draft into scratch for direct command consumption
    scratch = ROOT / "scratch"
    scratch.mkdir(exist_ok=True)
    (scratch / "post.txt").write_text(text, encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="OmniPost Zero-Cost Schedule Gate")
    ap.add_argument("--wake", action="store_true",
                    help="print full instruction block for an LLM agent, not just JSON")
    args = ap.parse_args()
    return check_gate(wake=args.wake)


if __name__ == "__main__":
    sys.exit(main())
