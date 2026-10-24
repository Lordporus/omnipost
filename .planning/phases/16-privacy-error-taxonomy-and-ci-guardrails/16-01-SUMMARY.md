# Phase 16 Plan 01 Summary

**Status:** Complete

**Branch:** `phase-16-privacy-ci-guardrails` (stacked on `phase-15-storybook-renderer` @ `8f6d2e5`)

## What changed

### Task 1 — private, redacted, bounded artifacts

- Rewrote `capture_failure_artifacts` in `adapters/base.py`:
  - Writes under `ROOT / "shots"` (`Path(__file__).resolve().parent.parent`), never a
    CWD-relative path.
  - Names files `{platform}_{UTC timestamp}.png/.html` instead of fixed overwrite
    names.
  - Returns a short `summary` plus artifact paths; it never returns raw DOM.
  - Logs screenshot/DOM capture failures at warning level so they cannot mask the
    adapter error that triggered the capture.
- Added `redact_text`:
  - Emails → `[REDACTED_EMAIL]`.
  - `Authorization`/`Proxy-Authorization`/`Bearer`/`Cookie`/`Set-Cookie`/CSRF/
    session/token patterns → `[REDACTED]`.
  - 32+ character base64/hex secrets → `[REDACTED_SECRET]`.
- Added `redact_html`: strips `<script>` bodies, redacts `<input value>` and
  `<textarea>` contents, then applies `redact_text`.
- Added `_enforce_retention(platform, keep=20)`: keeps the newest 20 artifact files
  per platform and deletes older ones.
- Verified `scripts/notify.py` and `scripts/notify_webhook.py` already send only
  summaries and metadata; no raw DOM or screenshots are attached.

### Task 2 — typed error taxonomy in adapters

- `scripts/errors.py` already owns the shared hierarchy (`AdapterError`,
  `SelectorError`, `ComposerOpenError`, `VerificationError`, `RateLimitError`).
  No duplicate classes were added, and `StateCorruptionError`/`StateLockTimeout`
  remain `StateError` subclasses.
- `adapters/base.py` re-exports only the adapter-facing classes for compatibility.
- Removed every `except Exception: pass` and `except Exception: continue` from the
  adapters:
  - `linkedin.py`: four polling loops now catch
    `(CDPError, OSError, asyncio.TimeoutError, ValueError)`; file-input and
    verification paths catch the same specific set.
  - `threads.py`: browser-tab detection and media polling narrowed; `check_session`
    catches `(AdapterError, CDPError, OSError, asyncio.TimeoutError, RuntimeError,
    ValueError)`.
  - `x.py`: `verify` narrows to `(CDPError, OSError, asyncio.TimeoutError,
    ValueError)`.
  - `bluesky.py`: JSON error-body parsing narrows to `(ValueError, TypeError)`;
    session/publish/verify catch `(RuntimeError, OSError, ValueError, KeyError,
    urllib.error.URLError)`.
- The main selector-miss paths already raise contextual errors: LinkedIn raises
  `ComposerOpenError` with selector list/candidate count, Threads raises
  `SelectorError` with selector and submit context.
- `RenderError` (Phase 15) and `CopyValidationError`/`MediaContractError`
  (Phase 14) were left untouched.

### Task 3 — fixture-DOM selector contracts

- Added sanitized fixtures under `tests/fixtures/dom/`:
  - `linkedin_feed.html` (share-box trigger, tertiary Like/Comment decoys, composer
    dialog, editor, Post button, image input).
  - `threads_composer.html` (Create trigger, lexical editor, Post button, `/post/`
    toast anchor, image input).
  - `x_composer.html` (`tweetTextarea_0`, `tweetButton`, `fileInput`, Like decoy).
- Added `tests/test_selector_contracts.py` with the six plan tests: exactly one
  share-box trigger, tertiary buttons not used as fallbacks, LinkedIn dialog/editor,
  Threads permalink, X submit/media, and a missing selector raising `SelectorError`
  with platform/stage/selector/context.
- Fixtures contain no names, emails, cookies, tokens, or network calls.

### Task 4 — 9:16 goldens and manual live smoke

- Kept the PDF carousel test at `1080x1080`; `render/carousel.py` was not changed.
- The storybook tests still assert `1080x1920` at `scale=1.0` and `2160x3840` at
  `scale=2.0`; the fast template/content tests do not need a browser.
- Added `test_embedded_font_css_present` (three vendored faces, no `https://`).
- Extended `.github/workflows/ci.yml` with a contract/privacy/golden step after the
  full suite, keeping the Ubuntu/Windows × Python 3.10–3.12 matrix and requiring no
  live credentials.
- Added `.github/workflows/live-smoke.yml`:
  - `workflow_dispatch` only (no `push` or `pull_request`).
  - `live_publish` defaults to `false`, so the default command is
    `python scripts/publish_now.py --fresh --platforms <...> --dry-run`.
  - Platform session and notification secrets are injected from repository
    secrets.

### Task 5 — privacy regression tests

- Added `tests/test_artifact_privacy.py` with seven tests:
  1. `test_artifacts_under_root` (and the written HTML is redacted).
  2. `test_redacts_email`.
  3. `test_redacts_auth_headers` (Bearer, cookies, CSRF, short token).
  4. `test_redacts_long_secrets` (40-character token).
  5. `test_retention_caps_files` (25 → 20).
  6. `test_notification_has_no_raw_dom`.
  7. `test_capture_failure_does_not_mask`.
- Added the privacy file to the CI contract step.

## Verification

- `py -3.12 -m pytest tests/test_artifact_privacy.py -q` → **7 passed**
- `py -3.12 -m pytest tests/test_selector_contracts.py -q` → **6 passed**
- `py -3.12 -m pytest tests/test_storybook_render.py tests/test_selector_contracts.py -q`
  → **15 passed**
- `py -3.12 -m pytest tests/test_artifact_privacy.py tests/test_selector_contracts.py tests/test_carousel_rendering.py -q`
  → **18 passed, 1 warning**
- `py -3.12 -m py_compile adapters/base.py adapters/linkedin.py adapters/threads.py adapters/x.py adapters/bluesky.py`
  → **passing**
- No `except Exception: pass`/`continue` remains in `adapters/`.
- `.github/workflows/live-smoke.yml` contains only `workflow_dispatch` (no `push:` or
  `pull_request:`).
- Full repository suite: **303 passed, 4 warnings**.

## Notes

- No live content was published.
- The PDF carousel remains `1080x1080`; only the storybook renderer is 9:16.
- Media-attachment degradation (LinkedIn/Threads continue text-only when a file input
  never appears) is unchanged; composer and submit selector misses raise typed errors.
- `capture_failure_artifacts` deliberately catches capture-side exceptions with
  logging so the original adapter error is preserved; this is not a silent `pass`.
- The three pre-existing mock `coroutine ... was never awaited` warnings remain and
  are not failures.
