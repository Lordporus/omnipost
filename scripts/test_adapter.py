#!/usr/bin/env python
"""Isolated Single-Platform Diagnostic & Test Harness for OmniPost.

Allows rapid, isolated testing of a single platform adapter (X, Bluesky, LinkedIn, Threads)
without triggering the other platforms or risking cascading partial failures.
Automatically surfaces failure screenshots and DOM snapshots upon errors.

Usage:
  python scripts/test_adapter.py --platform bluesky --dry-run
  python scripts/test_adapter.py --platform x --text "Testing single adapter probe"
  python scripts/test_adapter.py --platform linkedin --pdf scratch/carousels/architecture_carousel.pdf
  python scripts/test_adapter.py --platform threads --draft drafts/2026-10-18.json --slot 20:00
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from adapters.base import PublishPayload, PublishResult
from adapters.bluesky import BlueskyAdapter
from adapters.linkedin import LinkedInAdapter
from adapters.threads import ThreadsAdapter
from adapters.x import XAdapter
import settings

ADAPTERS = {
    "x": XAdapter,
    "bluesky": BlueskyAdapter,
    "linkedin": LinkedInAdapter,
    "threads": ThreadsAdapter,
}


def load_from_draft(draft_path: Path, platform: str, slot: str | None = None) -> tuple[str, list[Path], str, str]:
    """Extract tailored text, media paths, and media type from a draft JSON."""
    if not draft_path.exists():
        raise FileNotFoundError(f"Draft file not found: {draft_path}")

    data = json.loads(draft_path.read_text(encoding="utf-8"))
    if "slots" in data and isinstance(data["slots"], list) and len(data["slots"]) > 0:
        selected = None
        if slot:
            selected = next((s for s in data["slots"] if s.get("slot") == slot.strip()), None)
            if not selected:
                available = [s.get("slot") for s in data["slots"]]
                raise ValueError(f"Slot '{slot}' not found. Available: {available}")
        else:
            selected = next((s for s in data["slots"] if not s.get("posted", False)), data["slots"][0])
        data = selected

    plat_dict = data.get("platforms", {}).get(platform.lower(), {})
    text = plat_dict.get("text") or data.get("text") or data.get("headline") or ""
    media_raw = plat_dict.get("media") or ([data["image"]] if data.get("image") else [])
    media_paths = [ROOT / m if not Path(m).is_absolute() else Path(m) for m in media_raw]
    media_type = plat_dict.get("media_type") or ("carousel" if any(p.suffix.lower() == ".pdf" for p in media_paths) else "image")
    doc_title = plat_dict.get("document_title") or data.get("headline", "")[:50]
    return text, media_paths, media_type, doc_title


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniPost Single-Platform Diagnostic Runner")
    parser.add_argument("--platform", required=True, choices=["x", "bluesky", "linkedin", "threads"],
                        help="Target platform to test in isolation")
    parser.add_argument("--text", help="Explicit text to post")
    parser.add_argument("--media", help="Path to image file to attach")
    parser.add_argument("--pdf", help="Path to PDF carousel document to attach")
    parser.add_argument("--draft", help="Path to draft JSON file")
    parser.add_argument("--slot", help="Time slot from draft JSON (e.g. 20:00)")
    parser.add_argument("--dry-run", action="store_true", help="Perform session check and limit validation only")
    parser.add_argument("--timeout", type=float, default=80.0, help="Timeout in seconds for operations")
    args = parser.parse_args()

    plat = args.platform.lower()
    adapter_cls = ADAPTERS.get(plat)
    if not adapter_cls:
        print(f"[ERROR] Unknown platform '{plat}'", file=sys.stderr)
        return 1

    adapter = adapter_cls()
    print("=" * 60)
    print(f"OmniPost Diagnostic Harness: Platform [{plat.upper()}]")
    print("=" * 60)

    # 1. Pre-flight Session Check
    print(f"[*] Checking session readiness for {plat.upper()}...")
    session = adapter.check_session()
    print(f"  Session OK: {session.get('ok')}")
    print(f"  Account:    {session.get('handle')}")
    if session.get("error"):
        print(f"  Session Error: {session.get('error')}", file=sys.stderr)

    if not session.get("ok") and not args.dry_run:
        print(f"[ERROR] Cannot proceed: {plat.upper()} session is not ready.", file=sys.stderr)
        return 1

    # 2. Extract or Resolve Payload
    text = args.text or ""
    media_paths: list[Path] = []
    media_type = "image"
    doc_title = ""

    if args.draft:
        try:
            t, m, m_type, d_title = load_from_draft(Path(args.draft), plat, args.slot)
            if not text:
                text = t
            if not media_paths:
                media_paths = m
            media_type = m_type
            doc_title = d_title
        except Exception as exc:
            print(f"[ERROR] Failed to read draft: {exc}", file=sys.stderr)
            return 1

    if args.pdf:
        pdf_path = Path(args.pdf) if Path(args.pdf).is_absolute() else ROOT / args.pdf
        media_paths = [pdf_path]
        media_type = "carousel"
        if not doc_title:
            doc_title = pdf_path.stem.replace("_", " ").title()[:50]

    if args.media:
        med_path = Path(args.media) if Path(args.media).is_absolute() else ROOT / args.media
        media_paths = [med_path]
        media_type = "image"

    if not text:
        text = f"OmniPost diagnostic probe on {plat.upper()} at {time.strftime('%Y-%m-%d %H:%M:%S')}"

    # 3. Check Limits
    caps = adapter.capabilities
    char_count = len(text)
    fits_limit = char_count <= caps.max_characters
    print(f"[*] Character Count: {char_count}/{caps.max_characters} (Within limit: {fits_limit})")
    print(f"[*] Media: {len(media_paths)} items ({media_type})")
    if media_paths:
        for p in media_paths:
            print(f"    - {p} (exists: {p.exists()})")

    if not fits_limit:
        print(f"[ERROR] Text exceeds character limit for {plat.upper()} ({char_count} > {caps.max_characters})", file=sys.stderr)
        return 1

    if args.dry_run:
        print("\n[PASS] Dry run complete. Platform adapter is ready for live publishing.")
        return 0

    # 4. Execute Isolated Live Publish
    payload = PublishPayload(
        text=text,
        media_paths=media_paths,
        media_type=media_type,
        extra_metadata={"document_title": doc_title} if doc_title else {},
    )

    print(f"\n[*] Executing live publish on [{plat.upper()}] (max {args.timeout}s)...")
    start_t = time.time()
    try:
        result: PublishResult = adapter.publish(payload)
        elapsed = time.time() - start_t
        print(f"[*] Finished in {elapsed:.2f}s")

        if result.success:
            print("\n" + "=" * 25 + " SUCCESS " + "=" * 25)
            print(f"  Platform: {result.platform.upper()}")
            print(f"  URL:      {result.url}")
            print(f"  Verified: {result.verified}")
            print(f"  Post ID:  {result.post_id}")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 25 + " FAILED " + "=" * 26)
            print(f"  Platform: {result.platform.upper()}")
            print(f"  Error:    {result.error}")
            if result.artifacts:
                for k, v in result.artifacts.items():
                    print(f"  Artifact ({k}): {v}")
            # Check if any failure screenshot exists
            fail_shot = ROOT / "shots" / f"{plat}_fail.png"
            if fail_shot.exists():
                print(f"  Captured Failure Screenshot: {fail_shot}")
            print("=" * 60)
            return 1
    except Exception as exc:
        elapsed = time.time() - start_t
        print(f"\n[EXCEPTION] Adapter publish crashed after {elapsed:.2f}s: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
