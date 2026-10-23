# Phase 13 Plan 01 Summary

**Status:** Complete

**Branch:** `phase-11-content-integrity` (Phase 13 implemented on the existing branch)

## What changed

- Added typed adapter failures in `scripts/errors.py` and re-exported them from `adapters/base.py`:
  - `AdapterError` carries `platform`, `stage`, and structured `context`.
  - `SelectorError` records the selector, selector candidates, and candidate count.
  - `ComposerOpenError` extends `SelectorError` and carries failure artifacts.
  - `VerificationError` carries the attempted URL/post id.
  - `RateLimitError` defaults to `platform="linkedin"`, `stage="rate_limit"`, and fails closed.
- Recovered LinkedIn composer detection:
  - Replaced the ad-hoc click chain with scoped share-box selectors and a structured `{result, selector, candidates}` trigger result.
  - Removed the generic tertiary artdeco button fallback that could click Like/Comment.
  - Added a dialog/editor readiness poll that checks visibility, enabled state, focus, and `document.activeElement` before typing.
  - Composer failures now raise `ComposerOpenError` with selectors, candidate count, trigger diagnostics, and screenshot artifacts.
  - A failed PDF carousel attachment now fails the publish instead of silently publishing text-only.
- Repaired LinkedIn rate limiting:
  - Reads `posts[*].platforms.linkedin.at` from schema v3.
  - Ignores legacy `outcomes` and entry-level `platform`/`at` fields.
  - Parses timestamps timezone-aware, treating naive values as UTC.
  - Any unreadable state or malformed timestamp raises `RateLimitError` and blocks the publish.
- Made Threads results honest:
  - Polls the success toast and latest activity item for a real `/post/` permalink.
  - Returns that permalink and extracts the post id.
  - Falls back to `_async_verify` read-back when no permalink appears.
  - Never returns the profile URL as `url`; the profile URL is exposed only in `raw_response["profile_url"]`.
  - Keeps `success=True` for submitted-but-unverified posts so Phase 12 records `submitted_unverified`.
  - `verify()` now delegates directly to `_async_verify` for Phase 12 reconciliation.
  - Removed the redundant broad exception tuple and narrowed verification error handling.
- Attached all X cards:
  - `XAdapter` passes the full ordered media list up to `max_images`.
  - `scripts/post.py` accepts `images: list[Path] | None`, attaches all files in one `DOM.setFileInputFiles` call, and preserves the single-image `image=` path.
  - The attach status/log includes the number of cards attached.
- Added `tests/test_adapter_contracts.py` covering scoped composer selection, delayed dialog polling, v3 rate-limit reads, fail-closed rate limits, Threads toast permalinks, unverified Threads results, X multi-card dispatch, and typed-error context.
- Updated LinkedIn, LinkedIn carousel, and Threads tests for the new diagnostics, v3 state shape, focus readiness, and permalink behavior.

## Verification

- `py -3.12 -m pytest tests/test_adapter_contracts.py -q` → **8 passed**
- Targeted adapter suite (`test_linkedin`, `test_linkedin_carousel`, `test_threads`, `test_adapters`) → **32 passed**
- Full repository suite → **269 passed, 3 warnings**
- `py -3.12 -m py_compile` over all changed modules → **passing**
- `rg -n "artdeco-button--tertiary|base_url\}@" adapters` → **no matches**
- `AdapterError('x', platform='x').platform == 'x'` → **passing**
- `ThreadsAdapter.verify` is present and delegates to `_async_verify`.

## Notes

- No live content was published.
- The remaining warnings are mock-related `coroutine ... was never awaited` warnings, not failures.
- Phase 13 was implemented on the existing feature branch after Phase 12; nothing was merged or pushed.
