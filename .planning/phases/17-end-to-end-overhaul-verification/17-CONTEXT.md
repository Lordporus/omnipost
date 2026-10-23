# Phase 17: End-to-End Overhaul Verification & Live Drop - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase is the acceptance gate for the overhaul. It proves that Phases 11–16 work together and performs one controlled live drop. It does **not** introduce new product features; defects found here go back to the owning phase.

Source of truth: `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §5 Step 4, §7 acceptance criteria.

</domain>

<decisions>
## Implementation Decisions

### Deterministic proof
- **D-01:** Build a single `scripts/verify_overhaul.py` (or extend `scripts/doctor.py`) that checks: relevance rejection, fail-closed synthesis, cross-slot uniqueness, state status semantics, platform limits, 9:16 dimensions, embedded fonts/offline render, and media contract.
- **D-02:** The verifier runs two different source topics and asserts different bullets, takeaways, and slide content.
- **D-03:** The dry-run `python scripts/publish_now.py --fresh --dry-run` must show relevant copy, correct limits, and 9:16 assets for every slot.

### Live proof
- **D-04:** A live drop is a manual checkpoint, not automatic. It targets all enabled platforms and records `success`, `verified`, URL, content hash, asset dimensions, and limit counts.
- **D-05:** After the drop, rerun the same slot and confirm idempotency prevents a duplicate; force a timeout in a controlled test and confirm reconciliation does not duplicate.
- **D-06:** Write `docs/OVERHAUL_VERIFICATION.md` with per-platform evidence and a clear PASS/UNVERIFIED/FAIL table.

### Claude's Discretion
- Whether the verifier is a new script or a `doctor.py` subcommand.
- Report format details, as long as it is machine-readable JSON plus a human-readable Markdown summary.

</decisions>

<specifics>
## Specific Ideas

- The acceptance table must mirror the MD: political HN item rejected; two topics differ; Threads unverified until permalink; timeout never duplicates; emoji/CJK limits pass; cards 1080×1920 offline.
- The live drop must not be triggered by CI on push/PR.

</specifics>

<canonical_refs>
## Canonical References

- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §5 Step 4 — end-to-end verification.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §7 — acceptance criteria.
- `scripts/publish_now.py`, `scripts/doctor.py`, `scripts/analytics.py`.
- `drafts/`, `state.json`, `docs/`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/doctor.py` already probes browser/session/research health; add an overhaul section rather than duplicating probes.
- `publish_now` already supports `--dry-run`, `--fresh`, and per-platform selection; reuse those paths.
- `state.json` is the source of truth for post status; the verifier should read it, not re-derive.

### Established Patterns
- Live tests are manual and supervised; automated tests must not post.
- Reports are written to `docs/` and committed with the phase.

### Integration Points
- The verifier consumes outputs from `generate`, `repurpose`, `render`, `ledger`, and the adapters.
- The live drop uses the same `publish_now` path users run, not a test-only shortcut.

</code_context>

<deferred>
## Deferred Ideas

- Continuous live monitoring/alerting.
- Multi-day performance benchmarking.
- Additional platform expansion.

</deferred>

---

*Phase: 17-end-to-end-overhaul-verification*
*Context gathered: 2026-10-23*
