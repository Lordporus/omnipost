#!/usr/bin/env python
"""Unified State Ledger (Schema v3.0) for OmniPost.

Maintains truthful, per-platform publishing status in state.json:
  - published_verified: the post was confirmed live.
  - submitted_unverified: the platform accepted a submission but read-back did not confirm it.
  - failed: the publish attempt did not succeed.
  - pending: an idempotency reservation exists but no result has been recorded yet.

State reads and writes are serialized with a cross-process lock, writes are
atomic, a validated backup is refreshed on every save, and corrupt state is
quarantined instead of being silently replaced with an empty document.
"""
from __future__ import annotations

import errno
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import settings  # noqa: E402
from adapters.base import PublishResult  # noqa: E402

try:
    from scripts.errors import StateCorruptionError, StateError, StateLockTimeout
except ImportError:  # direct script execution
    from errors import StateCorruptionError, StateError, StateLockTimeout

STATE_PATH = ROOT / "state.json"
CURRENT_SCHEMA_VERSION = "3.0"

STATUS_PUBLISHED_VERIFIED = "published_verified"
STATUS_SUBMITTED_UNVERIFIED = "submitted_unverified"
STATUS_FAILED = "failed"
STATUS_PENDING = "pending"

_HELD_LOCKS = threading.local()
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _held_locks() -> set[str]:
    locks = getattr(_HELD_LOCKS, "paths", None)
    if locks is None:
        locks = set()
        _HELD_LOCKS.paths = locks
    return locks


def _resolved(path: Path) -> str:
    return str(path.resolve())


def _thread_lock_for(lock_path: Path) -> threading.Lock:
    key = _resolved(lock_path)
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[key] = lock
        return lock


def _ensure_lock_byte(lock_file: Any) -> None:
    lock_file.seek(0, os.SEEK_END)
    if lock_file.tell() == 0:
        lock_file.write(b"\0")
        lock_file.flush()
    lock_file.seek(0)


def _acquire_os_lock(lock_file: Any, timeout: float) -> None:
    started = time.monotonic()
    while True:
        try:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as exc:
            if time.monotonic() - started >= timeout:
                raise StateLockTimeout(
                    f"timed out after {timeout:.1f}s waiting for state lock"
                ) from exc
            time.sleep(0.05)


def _release_os_lock(lock_file: Any) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def _state_lock(target: Path, timeout: float = 30.0) -> Iterator[None]:
    """Serialize state access across threads and processes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    thread_lock = _thread_lock_for(lock_path)
    if not thread_lock.acquire(timeout=timeout):
        raise StateLockTimeout(f"timed out after {timeout:.1f}s waiting for state lock")

    lock_file = None
    try:
        lock_file = open(lock_path, "a+b")
        if os.name == "nt":
            _ensure_lock_byte(lock_file)
        _acquire_os_lock(lock_file, timeout)
        yield
    finally:
        if lock_file is not None:
            _release_os_lock(lock_file)
            lock_file.close()
        thread_lock.release()


def _atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.parent / (
        f"{target.name}.tmp.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}"
    )
    try:
        tmp_path.write_text(content, encoding="utf-8")
        try:
            os.replace(tmp_path, target)
        except OSError as err:
            if getattr(err, "errno", None) in (errno.EBUSY, errno.EXDEV, errno.EPERM):
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
            else:
                raise
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _save_state_locked(data: dict, target: Path) -> None:
    """Write state atomically and refresh the validated backup. Caller holds the lock."""
    content = json.dumps(data, indent=2, ensure_ascii=False)
    json.loads(content)  # validate before either file is touched
    _atomic_write_text(target, content)
    backup = target.with_name(target.name + ".bak")
    _atomic_write_text(backup, content)


def _clean_state() -> dict:
    try:
        cfg = settings.load()
    except Exception:
        cfg = {}
    return {
        "version": CURRENT_SCHEMA_VERSION,
        "handle": cfg.get("handle", ""),
        "ai_update_day": 0,
        "last_ai_update": None,
        "posts": [],
    }


def _quarantine_corrupt(target: Path, exc: Exception) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    corrupt_path = target.with_name(f"{target.name}.corrupt.{timestamp}")
    try:
        os.replace(target, corrupt_path)
    except OSError:
        try:
            corrupt_path.write_bytes(target.read_bytes())
            target.unlink()
        except OSError:
            pass
    print(
        f"[WARN] Failed to read {target}: {exc}. Quarantined as {corrupt_path}.",
        file=sys.stderr,
    )
    return corrupt_path


def migrate_state(data: dict) -> dict:
    """Migrate legacy state to schema v3.0 without losing history or unknown fields."""
    if not isinstance(data, dict):
        raise ValueError("state root must be a JSON object")

    version = str(data.get("version", "1.0"))
    migrated = dict(data)
    migrated["version"] = CURRENT_SCHEMA_VERSION
    if version != CURRENT_SCHEMA_VERSION:
        migrated.setdefault("migrated_from", version)

    posts = data.get("posts", [])
    if not isinstance(posts, list):
        raise ValueError("state.posts must be a list")

    migrated_posts = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        p_copy = dict(post)
        platforms = p_copy.get("platforms")

        if not isinstance(platforms, dict):
            platforms = {}
            tweet_url = p_copy.get("tweet_url")
            verified = bool(p_copy.get("verified", False))
            platform_name = p_copy.get("platform") or "x"
            if verified:
                status = STATUS_PUBLISHED_VERIFIED
            elif tweet_url:
                status = STATUS_SUBMITTED_UNVERIFIED
            else:
                status = STATUS_FAILED
            platforms[platform_name] = {
                "status": status,
                "url": tweet_url or p_copy.get("url"),
                "verified": verified,
                "at": p_copy.get("at"),
                "error": p_copy.get("error"),
            }
        else:
            normalized = {}
            for platform_name, record in platforms.items():
                if not isinstance(record, dict):
                    normalized[platform_name] = {"status": str(record)}
                    continue
                rec = dict(record)
                if rec.get("status") == "published":
                    rec["status"] = (
                        STATUS_PUBLISHED_VERIFIED
                        if bool(rec.get("verified", False))
                        else STATUS_SUBMITTED_UNVERIFIED
                    )
                normalized[platform_name] = rec
            platforms = normalized

        p_copy["platforms"] = platforms

        if "date" not in p_copy:
            at_val = p_copy.get("at", "")
            if at_val:
                try:
                    p_copy["date"] = datetime.fromisoformat(
                        str(at_val).replace("Z", "+00:00")
                    ).strftime("%Y-%m-%d")
                except Exception:
                    p_copy["date"] = ""
            else:
                p_copy["date"] = ""

        migrated_posts.append(p_copy)

    migrated["posts"] = migrated_posts
    return migrated


def load_state(path: Path | None = None) -> dict:
    """Load and migrate state, quarantining corruption and restoring the backup."""
    target = Path(path) if path else STATE_PATH
    if not target.exists():
        return _clean_state()

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return migrate_state(raw)
    except Exception as exc:
        corrupt_path = _quarantine_corrupt(target, exc)
        backup = target.with_name(target.name + ".bak")
        if backup.exists():
            try:
                raw_backup = json.loads(backup.read_text(encoding="utf-8"))
                migrated = migrate_state(raw_backup)
                _atomic_write_text(
                    target,
                    json.dumps(migrated, indent=2, ensure_ascii=False),
                )
                print(
                    f"[WARN] Restored {target} from {backup.name}.",
                    file=sys.stderr,
                )
                return migrated
            except Exception as backup_exc:
                raise StateCorruptionError(
                    f"{target} is corrupt ({exc}); backup {backup.name} is unusable "
                    f"({backup_exc}); quarantined at {corrupt_path}"
                ) from backup_exc

        raise StateCorruptionError(
            f"{target} is corrupt ({exc}); no valid backup was available; "
            f"quarantined at {corrupt_path}"
        ) from exc


def save_state(data: dict, path: Path | None = None) -> None:
    """Atomically save state and refresh the backup, acquiring the lock if needed."""
    target = Path(path) if path else STATE_PATH
    if _resolved(target) in _held_locks():
        _save_state_locked(data, target)
        return

    with _state_lock(target):
        _save_state_locked(data, target)


@contextmanager
def state_transaction(path: Path | None = None, timeout: float = 30.0) -> Iterator[dict]:
    """Lock, load, yield for mutation, then atomically save on clean exit."""
    target = Path(path) if path else STATE_PATH
    with _state_lock(target, timeout=timeout):
        resolved = _resolved(target)
        _held_locks().add(resolved)
        try:
            state = load_state(target)
            yield state
            _save_state_locked(state, target)
        finally:
            _held_locks().discard(resolved)


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
    """Only a verified live post satisfies done."""
    status = get_platform_status(state, date, slot, platform)
    if not status:
        return False
    return status.get("status") == STATUS_PUBLISHED_VERIFIED


def get_pending_platforms(state: dict, date: str, slot: str, target_platforms: list[str]) -> list[str]:
    """Return platforms that are not verified, including unverified and failed ones."""
    return [p for p in target_platforms if not is_platform_done(state, date, slot, p)]


def is_slot_fully_published(state: dict, date: str, slot: str, target_platforms: list[str]) -> bool:
    """Return True only when every targeted platform is published_verified."""
    if not target_platforms:
        return False
    return len(get_pending_platforms(state, date, slot, target_platforms)) == 0


def has_idempotency_key(state: dict, key: str) -> bool:
    """Return True when the key is present at platform or slot level."""
    return get_idempotency_record(state, key) is not None


def get_idempotency_record(state: dict, key: str) -> dict | None:
    """Return the platform record carrying this idempotency key, if any."""
    for post in state.get("posts", []):
        if not isinstance(post, dict):
            continue
        keys = post.get("idempotency_keys")
        if isinstance(keys, dict) and key in keys:
            platform = keys[key]
            record = post.get("platforms", {}).get(platform)
            if isinstance(record, dict):
                return record
        for record in post.get("platforms", {}).values():
            if isinstance(record, dict) and record.get("idempotency_key") == key:
                return record
    return None


def reserve_idempotency(
    key: str,
    platform: str,
    force: bool = False,
    allow_failed: bool = False,
    path: Path | None = None,
    timeout: float = 30.0,
) -> bool:
    """Reserve a pending publish attempt before dispatch.

    The reservation is committed in its own transaction so two processes cannot
    both pass a read-only check and publish the same slot. Existing reservations
    are never overwritten unless force=True (or a failed record is explicitly
    retried with allow_failed=True).
    """
    try:
        date_slot, _key_platform = key.rsplit(":", 1)
        date, slot = date_slot.split(":", 1)
    except ValueError as exc:
        raise StateError(f"invalid idempotency key: {key}") from exc

    target = Path(path) if path else STATE_PATH
    with state_transaction(target, timeout=timeout) as state:
        existing = get_idempotency_record(state, key)
        if existing is not None and not force:
            if not (
                existing.get("status") == STATUS_FAILED and allow_failed
            ):
                return False

        attempt = int(existing.get("attempt", 1) or 1) + 1 if existing else 1
        now_iso = datetime.now(timezone.utc).isoformat()

        entry = get_slot_entry(state, date, slot)
        if not entry:
            entry = {
                "date": date,
                "slot": slot,
                "kind": "value",
                "at": now_iso,
                "text": "",
                "platforms": {},
            }
            state.setdefault("posts", []).append(entry)

        entry.setdefault("platforms", {})[platform] = {
            "status": STATUS_PENDING,
            "idempotency_key": key,
            "reserved_at": now_iso,
            "pid": os.getpid(),
            "attempt": attempt,
            "verified": False,
            "url": None,
            "post_id": None,
            "error": None,
            "at": None,
            "previous_status": existing.get("status") if existing else None,
            "previous_url": existing.get("url") if existing else None,
            "previous_error": existing.get("error") if existing else None,
        }
        entry.setdefault("idempotency_keys", {})[key] = platform
        return True


def _record_platform_status_locked(
    state: dict,
    date: str,
    slot: str,
    platform: str,
    result: PublishResult | dict[str, Any],
    text: str = "",
    kind: str = "value",
    idempotency_key: str | None = None,
) -> dict:
    """Record a result into an already-locked state dict."""
    if isinstance(result, PublishResult):
        success = result.success
        url = result.url
        verified = result.verified
        error = result.error
        post_id = result.post_id
    else:
        success = bool(result.get("success", False))
        url = result.get("url")
        verified = bool(result.get("verified", False))
        error = result.get("error")
        post_id = result.get("post_id")

    if success and verified:
        status = STATUS_PUBLISHED_VERIFIED
    elif success:
        status = STATUS_SUBMITTED_UNVERIFIED
    else:
        status = STATUS_FAILED

    now_iso = datetime.now(timezone.utc).isoformat()
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

    existing = entry.setdefault("platforms", {}).get(platform) or {}
    key = idempotency_key if idempotency_key is not None else existing.get("idempotency_key")

    entry["platforms"][platform] = {
        "status": status,
        "url": url,
        "post_id": post_id,
        "verified": bool(verified),
        "at": now_iso,
        "error": error,
        "idempotency_key": key,
        "attempt": int(existing.get("attempt", 1) or 1),
        "reserved_at": existing.get("reserved_at"),
    }
    if key:
        entry.setdefault("idempotency_keys", {})[key] = platform

    # Backward compatibility for readers that still look at top-level X fields.
    if platform == "x":
        if success:
            entry["tweet_url"] = url
            entry["at"] = now_iso
        entry["verified"] = bool(verified) if success else False

    if kind == "ai_update" and success:
        state["last_ai_update"] = now_iso

    return state


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
    idempotency_key: str | None = None,
) -> dict:
    """Record a platform result with a locked read-modify-write when persisting."""
    if not auto_save:
        return _record_platform_status_locked(
            state,
            date,
            slot,
            platform,
            result,
            text=text,
            kind=kind,
            idempotency_key=idempotency_key,
        )

    target = Path(path) if path else STATE_PATH
    with state_transaction(target) as fresh:
        _record_platform_status_locked(
            fresh,
            date,
            slot,
            platform,
            result,
            text=text,
            kind=kind,
            idempotency_key=idempotency_key,
        )
        state.clear()
        state.update(fresh)
    return state
