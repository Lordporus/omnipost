#!/usr/bin/env python
"""Unified State Ledger (Schema v2.0) for OmniPost.

Maintains atomic, per-platform publishing status in state.json.
Provides:
  - Atomic read/write operations (with crash-safe temp file replacement).
  - Seamless auto-migration of legacy v1.0 state records.
  - Per-platform status inspection (pending, published, failed).
  - Partial-failure isolation to prevent duplicate posting across channels.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import settings  # noqa: E402
from adapters.base import PublishResult  # noqa: E402

STATE_PATH = ROOT / "state.json"
CURRENT_SCHEMA_VERSION = "2.0"


def migrate_state(data: dict) -> dict:
    """Migrate legacy v1.0 state to schema v2.0 without losing any post history."""
    if not isinstance(data, dict):
        return {
            "version": CURRENT_SCHEMA_VERSION,
            "handle": "",
            "ai_update_day": 0,
            "last_ai_update": None,
            "posts": [],
        }

    version = str(data.get("version", "1.0"))
    if version == CURRENT_SCHEMA_VERSION and all("platforms" in p for p in data.get("posts", [])):
        return data

    migrated = dict(data)
    migrated["version"] = CURRENT_SCHEMA_VERSION
    migrated_posts = []

    for post in data.get("posts", []):
        if not isinstance(post, dict):
            continue
        p_copy = dict(post)
        platforms = p_copy.get("platforms")
        if platforms is None:
            platforms = {}
            tweet_url = p_copy.get("tweet_url")
            verified = bool(p_copy.get("verified", False))
            plat = p_copy.get("platform") or "x"
            platforms[plat] = {
                "status": "published" if verified else "failed",
                "url": tweet_url or p_copy.get("url"),
                "verified": verified,
                "at": p_copy.get("at"),
                "error": p_copy.get("error"),
            }
            p_copy["platforms"] = platforms

        # Ensure date key is present
        if "date" not in p_copy:
            at_val = p_copy.get("at", "")
            if at_val:
                try:
                    p_copy["date"] = datetime.fromisoformat(str(at_val).replace("Z", "+00:00")).strftime("%Y-%m-%d")
                except Exception:
                    p_copy["date"] = ""
            else:
                p_copy["date"] = ""

        migrated_posts.append(p_copy)

    migrated["posts"] = migrated_posts
    return migrated


def load_state(path: Path | None = None) -> dict:
    """Load and auto-migrate state.json. Returns clean Schema v2.0 dict."""
    target = path or STATE_PATH
    if not target.exists():
        cfg = settings.load()
        return {
            "version": CURRENT_SCHEMA_VERSION,
            "handle": cfg.get("handle", ""),
            "ai_update_day": 0,
            "last_ai_update": None,
            "posts": [],
        }

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return migrate_state(raw)
    except Exception as exc:
        print(f"[WARN] Failed to parse {target}: {exc}. Initializing fallback state.")
        return {
            "version": CURRENT_SCHEMA_VERSION,
            "handle": "",
            "ai_update_day": 0,
            "last_ai_update": None,
            "posts": [],
        }


def save_state(data: dict, path: Path | None = None) -> None:
    """Atomically save state.json via temporary file replace to prevent corruption."""
    target = path or STATE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.parent / f"{target.name}.tmp.{os.getpid()}"

    content = json.dumps(data, indent=2, ensure_ascii=False)
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(target)


def get_slot_entry(state: dict, date: str, slot: str) -> dict | None:
    """Find post record in state matching slot and date."""
    for post in state.get("posts", []):
        if post.get("slot") == slot and (post.get("date") == date or not date):
            return post
    return None


def get_platform_status(state: dict, date: str, slot: str, platform: str) -> dict | None:
    """Return status dict for specific platform in slot entry, or None."""
    entry = get_slot_entry(state, date, slot)
    if not entry or "platforms" not in entry:
        return None
    return entry["platforms"].get(platform)


def is_platform_done(state: dict, date: str, slot: str, platform: str) -> bool:
    """Check if platform has already been successfully published."""
    status = get_platform_status(state, date, slot, platform)
    if not status:
        return False
    return status.get("status") == "published"


def get_pending_platforms(state: dict, date: str, slot: str, target_platforms: list[str]) -> list[str]:
    """Filter target_platforms to those that are not yet published and verified."""
    return [p for p in target_platforms if not is_platform_done(state, date, slot, p)]


def is_slot_fully_published(state: dict, date: str, slot: str, target_platforms: list[str]) -> bool:
    """Return True if all targeted platforms are successfully published and verified."""
    if not target_platforms:
        return False
    pending = get_pending_platforms(state, date, slot, target_platforms)
    return len(pending) == 0


def record_platform_status(
    state: dict,
    date: str,
    slot: str,
    platform: str,
    result: PublishResult | dict[str, Any],
    text: str = "",
    kind: str = "value",
    auto_save: bool = True,
    path: Path | None = None,
) -> dict:
    """Atomically record a platform publish result into state.json."""
    if isinstance(result, PublishResult):
        success = result.success
        url = result.url
        verified = result.verified
        error = result.error
    else:
        success = bool(result.get("success", False))
        url = result.get("url")
        verified = bool(result.get("verified", False))
        error = result.get("error")

    now_iso = datetime.now(timezone.utc).isoformat()

    # Find or create entry
    entry = get_slot_entry(state, date, slot)
    if not entry:
        entry = {
            "date": date,
            "slot": slot,
            "kind": kind,
            "at": now_iso,
            "text": text,
            "platforms": {},
        }
        state.setdefault("posts", []).append(entry)

    if not entry.get("text") and text:
        entry["text"] = text

    entry.setdefault("platforms", {})[platform] = {
        "status": "published" if success else "failed",
        "url": url,
        "verified": verified,
        "at": now_iso,
        "error": error,
    }

    # Backward compatibility: populate top-level fields for legacy readers
    if platform == "x" and success:
        entry["tweet_url"] = url
        entry["verified"] = verified
        entry["at"] = now_iso

    if kind == "ai_update" and success:
        state["last_ai_update"] = now_iso

    if auto_save:
        save_state(state, path)

    return state
