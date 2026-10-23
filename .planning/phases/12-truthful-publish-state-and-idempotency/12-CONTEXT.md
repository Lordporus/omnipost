# Phase 12: Truthful Publish State & Idempotency - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase owns `state.json` semantics and the publish dispatcher. It makes status truthful, serializes writes, cancels timed-out work, and prevents duplicate posts. It does **not** rewrite platform selectors (Phase 13), copy limits (Phase 14), or the renderer (Phase 15).

Source of truth: `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.4–6.7 and §7.

</domain>

<decisions>
## Implementation Decisions

### Status semantics
- **D-01:** Replace the binary `published`/`failed` status with `published_verified`, `submitted_unverified`, `failed`, and `pending`. Keep a read-time migration for v2 records: `published` + `verified=true` → `published_verified`; `published` + `verified=false` → `submitted_unverified`.
- **D-02:** `is_platform_done` is true only for `published_verified`. `get_pending_platforms` includes `submitted_unverified` so a later run can reconcile/retry it according to policy.
- **D-03:** `publish_now` must distinguish `[VERIFIED]`, `[UNVERIFIED]`, and `[FAIL]`; `all_ok` is true only when every result is verified.

### Locking and recovery
- **D-04:** Add a cross-process lock around the full state read-modify-write cycle. Use a lock file with an OS-appropriate primitive (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) and a bounded timeout; raise `StateLockTimeout` rather than silently dropping an update.
- **D-05:** On parse failure, quarantine the file as `state.json.corrupt.<timestamp>`, attempt `state.json.bak`, and raise `StateCorruptionError`. Never return an empty state that a later save can overwrite.
- **D-06:** Maintain a validated `state.json.bak` on every successful save.

### Timeout and idempotency
- **D-07:** A per-platform timeout must cancel the underlying work. Run each publish in a killable subprocess (or a worker with a hard cancellation primitive); do not rely on `ThreadPoolExecutor` + `future.result(timeout)` inside a `with` block, because `shutdown(wait=True)` defeats the timeout.
- **D-08:** Before recording a timeout as failed, reconcile against the platform using the adapter's recent-post/permalink check. If the post exists, record `submitted_unverified` or `published_verified`, never `failed`.
- **D-09:** Add an idempotency key `(date, slot, platform)` stored in state. Dispatch refuses a key that already exists unless `--force` is passed.
- **D-10:** Manual `publish_now` checks `is_platform_done` and the idempotency key before dispatch; `--force` is the only override.
- **D-11:** Offline connectivity returns a non-zero/deferred status, not `0`, so schedulers do not treat a skipped run as success.

### Claude's Discretion
- Lock implementation details and subprocess protocol (JSON stdin/stdout vs temporary result file).
- Whether the backup file is rotated or single-slot.

</decisions>

<specifics>
## Specific Ideas

- The live telemetry `[PASS] THREADS ... Verified: False` must become `[UNVERIFIED]` and must not satisfy `is_platform_done`.
- A timed-out LinkedIn publish that actually landed must not be retried; reconciliation must find the post before the next dispatch.
- Two simultaneous `publish_now` invocations must not both publish the same slot.

</specifics>

<canonical_refs>
## Canonical References

- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.4 — unverified recorded as published.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.5 — timeout/duplicate root cause.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.6 — manual dedupe and missing lock.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.7 — corrupt state wipe.
- `scripts/ledger.py`, `scripts/publish_now.py`, `scripts/autoposter.py`, `adapters/base.py`.
- `tests/test_ledger.py`, `tests/test_integration_e2e.py`, `tests/test_retry_isolation.py`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ledger.migrate_state`, `get_slot_entry`, `get_platform_status`, and `record_platform_status` form the core; extend rather than replace the public functions.
- `PublishResult` already carries `success`, `verified`, `url`, `post_id`, and `raw_response`; use those fields to derive status.
- `publish_now` already records results per platform and dispatches webhook summaries; preserve those surfaces while changing the meaning.

### Established Patterns
- State is a plain dict persisted as JSON; no database. The lock must wrap the dict mutation and save, not just the file write.
- Autoposter and manual publisher are separate entry points; both must share the same ledger API.

### Integration Points
- `adapters/*.publish` returns `PublishResult`.
- `scripts/autoposter.py` and `scripts/publish_now.py` call `record_platform_status`.
- `scripts/analytics.py` may read status fields; keep backward-compatible keys where practical.

</code_context>

<deferred>
## Deferred Ideas

- Database-backed state (JSON + lock is sufficient for this phase).
- Distributed locking across machines.
- Adapter-specific verification improvements — Phase 13.

</deferred>

---

*Phase: 12-truthful-publish-state-and-idempotency*
*Context gathered: 2026-10-23*
