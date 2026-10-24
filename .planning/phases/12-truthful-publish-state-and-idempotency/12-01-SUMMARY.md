# Phase 12 Plan 01 Summary

**Status:** Complete

**Branch:** `phase-11-content-integrity` (Phase 12 implemented on the existing branch)

## What changed

- Upgraded the ledger schema from `2.0` to `3.0` with four truthful statuses:
  - `published_verified`
  - `submitted_unverified`
  - `failed`
  - `pending`
- `is_platform_done` now returns true only for `published_verified`. Unverified submissions and failures remain visible through `get_pending_platforms`.
- Added read-time v2 migration:
  - `published` + `verified=true` → `published_verified`
  - `published` + `verified=false` → `submitted_unverified`
  - Unknown fields and top-level X `tweet_url`/`verified` are preserved.
- Added `StateError`, `StateCorruptionError`, and `StateLockTimeout` to `scripts/errors.py`.
- Added a cross-process/thread state transaction in `scripts/ledger.py`:
  - `msvcrt.locking` on Windows, `fcntl.flock` on POSIX, plus an in-process thread lock.
  - The lock covers load → mutate → save.
  - Atomic temp-file replacement and a refreshed validated `state.json.bak`.
  - Corrupt state is quarantined as `state.json.corrupt.<UTC timestamp>` and restored from backup; a corrupt file is never replaced with an empty state.
- Added `PublishPayload`/`PublishResult` JSON serialization contracts in `adapters/base.py`.
- Added `scripts/publish_worker.py`:
  - Reads JSON from stdin, resolves the adapter, publishes, and writes the authoritative result atomically to `--result-file`.
  - Redirects adapter stdout to stderr so adapter chatter cannot corrupt the result contract.
- Reworked `scripts/publish_now.py`:
  - Reserves an idempotency key before dispatch.
  - Uses a killable subprocess worker with a hard timeout.
  - Reconciles timed-out workers through `adapter.verify`; a timeout is never recorded as `failed` solely because the client timed out.
  - Skips already-published slots unless `--force`.
  - Retries failed records only with `--retry-failed`.
  - Prints `[VERIFIED]`, `[UNVERIFIED]`, `[FAIL]`, `[SKIP]`, and `[DEFERRED]` distinctly.
  - Live exit codes: `0` all verified, `1` any failed, `2` offline/deferred, `3` unverified-only.
- Added idempotency helpers to `scripts/ledger.py`:
  - `has_idempotency_key`
  - `get_idempotency_record`
  - `reserve_idempotency`
  - Reservations are committed in their own transaction before dispatch and include `reserved_at`, `pid`, and `attempt`.
- Updated `scripts/autoposter.py` to reserve keys before scheduled dispatch, never auto-retry `submitted_unverified`, and retry `failed` only when `publish.retry_failed` is true.
- Added `publish.retry_failed: false` defaults to `scripts/settings.py` and `config.example.json`.
- Updated status readers:
  - `due.py` treats only `published_verified` as done.
  - `validator.py` treats verified and unverified submissions as duplicates.
  - `analytics.py` analyzes only verified posts.
  - Notifications distinguish verified, unverified, and failed outcomes.
- Added `tests/test_state_truth.py` and `tests/test_idempotency.py`, including coverage for status truth, v2 migration, corruption quarantine, backup restore, lock serialization/timeout, duplicate/force publish, timeout kill/reconciliation, concurrent reservations, failed-retry policy, offline handling, dry-run state isolation, and worker result-file integrity.
- Updated existing ledger, e2e, retry-isolation, and repurposer tests for the v3 statuses and retry policy.

## Verification

- `py -3.12 -m pytest tests/test_state_truth.py tests/test_idempotency.py -q` → **18 passed**
- Targeted regression suite (`ledger`, `integration_e2e`, `retry_isolation`, `state_truth`, `idempotency`, `validator`, `analytics`, `notify`, `notify_webhook`, `guardrails`) → **79 passed**
- `py -3.12 -m py_compile` over all changed Python modules → **passing**
- `py -3.12 -c "import scripts.ledger, scripts.publish_now, scripts.publish_worker"` → **passing**
- `config.example.json` JSON validation → **passing**
- Full repository suite → **254 passed, 7 failed**. The 7 failures are the pre-existing LinkedIn/Threads adapter selector tests (`test_linkedin.py`, `test_linkedin_carousel.py`, `test_threads.py`) that fail on the browser composer focus path; they are unrelated to Phase 12.

## Notes

- No live content was published.
- The plan text says "fifteen tests"; the implemented suite has 18 because it also covers lock timeout, dry-run state isolation, and the worker result-file contract.
