# Phase 16: Privacy, Error Taxonomy & CI Guardrails - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase hardens failure artifacts, exception handling, and the test/CI surface. It does **not** add new product behavior; it makes the behavior from Phases 11–15 observable and regression-safe.

Source of truth: `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.15–6.17 and §7.

</domain>

<decisions>
## Implementation Decisions

### Artifact privacy
- **D-01:** Write screenshots and DOM dumps under `ROOT/shots`, never a CWD-relative path.
- **D-02:** Redact known PII and secrets before writing: emails, auth/cookie headers, CSRF tokens, and profile identifiers where practical. Cap retention (for example, keep the latest 20 files per platform).
- **D-03:** Never attach raw DOM or screenshots to webhook/Telegram notifications; send a path and a short summary only.

### Error taxonomy
- **D-04:** Define typed errors once in `scripts/errors.py`: `ContentError`/`TopicRejected`/`NoRelevantTopic`/`DuplicateTopic` (Phase 11), `StateError`/`StateCorruptionError`/`StateLockTimeout` (Phase 12), `AdapterError`/`SelectorError`/`ComposerOpenError`/`VerificationError`/`RateLimitError` (Phase 13), `CopyValidationError`/`MediaContractError` (Phase 14), and `RenderError` (Phase 15). `adapters/base.py` re-exports the adapter-facing classes; no phase redefines them.
- **D-05:** Replace broad `except Exception: pass` blocks in adapters with specific catches and contextual logging. Unexpected exceptions propagate and fail the platform.
- **D-06:** Keep top-level publish boundaries catching typed errors only; convert unknown exceptions into a typed `AdapterError` with a stack trace in the log.

### CI and tests
- **D-07:** Add fixture-DOM contract tests for the LinkedIn composer, Threads composer/permalink, and X submit button. Fixtures live under `tests/fixtures/dom/`.
- **D-08:** Add 9:16 golden-image tests that assert dimensions and offline rendering; update or replace tests that pin 1080×1080 as the only valid size.
- **D-09:** Add a `workflow_dispatch` live smoke job that is never run on push/PR and requires repository secrets.
- **D-10:** CI must run the full pytest suite plus the new contract/golden tests on Ubuntu and Windows.

### Claude's Discretion
- Redaction regex set and retention count.
- Whether fixture DOM tests use a headless browser or a pure HTML parser.

</decisions>

<specifics>
## Specific Ideas

- `shots/linkedin_fail.html` currently contains a full logged-in feed DOM; the new artifact writer must not produce an unredacted equivalent.
- The test suite must fail if a card is 1080×1080 or if a LinkedIn selector falls back to `artdeco-button--tertiary`.
- Live smoke tests must be opt-in, not a flaky PR gate.

</specifics>

<canonical_refs>
## Canonical References

- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.15 — artifact DOM leak.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.16 — broad exception handling.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.17 — CI gaps.
- `adapters/base.py`, `adapters/linkedin.py`, `adapters/threads.py`, `adapters/x.py`.
- `.github/workflows/ci.yml`, `tests/`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `capture_failure_artifacts` already captures screenshot + outerHTML; add path resolution, redaction, and retention.
- `PublishResult.artifacts` already carries paths; keep it.
- CI already runs `pytest -v` on Ubuntu/Windows and Python 3.10–3.12; extend it rather than replacing it.

### Established Patterns
- Tests use pytest and mock CDP/network; fixture DOM tests should follow the same no-live-browser pattern where possible.
- `.gitignore` already excludes `shots/`; keep it ignored.

### Integration Points
- Every adapter calls `capture_failure_artifacts`.
- `publish_now` and `autoposter` dispatch webhook summaries; they must not include raw DOM.
- CI is the final guardrail for dimensions, selectors, and privacy.

</code_context>

<deferred>
## Deferred Ideas

- Full browser-based visual regression (golden images are sufficient for dimensions/offline).
- External error reporting/Sentry integration.
- Credential rotation automation.

</deferred>

---

*Phase: 16-privacy-error-taxonomy-and-ci-guardrails*
*Context gathered: 2026-10-23*
