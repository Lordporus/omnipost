# Phase 13: Platform Adapter Recovery & Permalinks - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase owns the browser/CDP adapters for LinkedIn, Threads, and X: composer detection, rate limiting, post permalink extraction, and media attachment. It does **not** change state semantics (Phase 12), copy limits (Phase 14), or rendering (Phase 15).

Source of truth: `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §3, §6.8–6.10, and §7.

</domain>

<decisions>
## Implementation Decisions

### LinkedIn composer
- **D-01:** Detect the composer through scoped, resilient selectors: the share-box container first, then `[role="button"]`/`aria-label` text matches. Remove the generic `button.artdeco-button--tertiary` fallback because it can click Like/Comment.
- **D-02:** After clicking, poll for the composer dialog and editor to be visible and enabled; assert the editor has focus before typing. Do not rely on a fixed 2-second sleep.
- **D-03:** If the composer cannot be opened, capture redacted artifacts and raise a typed `ComposerOpenError` with the selector attempts that were made.

### LinkedIn rate limit
- **D-04:** Read the timestamp from `platforms.linkedin.at`, not the legacy `outcomes` key or the entry-level `at`.
- **D-05:** Parse timezone-aware ISO timestamps; treat naive timestamps as UTC. On any parse/read error, fail closed and raise `RateLimitError` rather than returning `True`.

### Threads and X
- **D-06:** After submission, extract the real Threads permalink from the success toast or the latest activity item. If it cannot be found, return `verified=False` and keep the profile URL only in `raw_response`; never set it as `url`.
- **D-07:** X attaches all `payload.media_paths` up to `max_images` (4), preserving order; do not silently drop cards 2–3.
- **D-08:** Adapter failures use typed errors (`SelectorError`, `ComposerOpenError`, `VerificationError`, `RateLimitError`) with platform, stage, and selector context.

### Claude's Discretion
- Exact polling interval/timeout for the composer and verification loops.
- Whether the Threads permalink comes from the toast anchor or the activity DOM first.

</decisions>

<specifics>
## Specific Ideas

- The observed failure `Could not find 'Start a post' button on LinkedIn feed` must become an actionable error that names the selectors tried and includes a redacted screenshot path.
- The observed `Verified: False - profile fallback` must never be reported as a verified post URL.
- A 2–3 card storybook must appear as 2–3 images on X, not one.

</specifics>

<canonical_refs>
## Canonical References

- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §3.1 — LinkedIn composer detection.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §3.2 — Threads verification fallback.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.8–6.10 — rate limit, wrong control, profile URL/X media.
- `adapters/linkedin.py`, `adapters/threads.py`, `adapters/x.py`, `adapters/base.py`.
- `tests/test_linkedin.py`, `tests/test_threads.py`, `tests/test_x.py` (or equivalent).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- LinkedIn already has `TRIGGER_COMPOSER_JS`, `FOCUS_EDITOR_JS`, `SUBMIT_POST_JS`, and `TOAST_QUERY_JS`; tighten and reuse them instead of adding a parallel path.
- Threads already has a `_async_verify` loop and toast handling; extend it to return the permalink.
- X delegates to `scripts/post.py`; pass all image paths through the existing `do_post` media contract.

### Established Patterns
- Adapters are synchronous `publish()` wrappers around `asyncio.run(_async_publish())`.
- `check_session()` and `publish()` return dictionaries/`PublishResult`; keep those contracts.
- Failure artifacts are captured through `adapters.base.capture_failure_artifacts`.

### Integration Points
- `publish_now` and `autoposter` call adapter `publish`.
- Phase 12's status semantics consume `success`, `verified`, and `url`; the adapter must not fake any of them.

</code_context>

<deferred>
## Deferred Ideas

- LinkedIn/Threads API-based publishing (browser automation remains the chosen path).
- Multi-account support.
- Rate-limit policy changes beyond the 4-hour LinkedIn gap.

</deferred>

---

*Phase: 13-platform-adapter-recovery-and-permalinks*
*Context gathered: 2026-10-23*
