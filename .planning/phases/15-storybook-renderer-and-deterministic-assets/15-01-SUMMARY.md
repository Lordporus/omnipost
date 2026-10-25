# Phase 15 Plan 01 Summary

**Status:** Complete

**Branch:** `phase-15-storybook-renderer` (cut from `origin/main` after PR #5 merged)

## What changed

- Rewrote `render/card_template.html` as a 9:16 storybook canvas:
  - `html, body, .card` are `1080x1920` with `overflow: hidden`.
  - Three-band grid: header `288px`, fluid hero, footer `192px`.
  - Header carries the brand dot, handle, category pill, and `01 / 03` pagination
    over a 2px emerald rule.
  - Hero holds the headline, body, and a bordered diagram/comparison panel built
    with grid/flex (no absolute positioning that can overflow).
  - Footer renders the real source domain, timestamp, and a page label; it never
    renders the literal `Verified Reference`.
  - Living palette: `#0D1117` canvas, `#00E599` emerald, `#8B5CF6` violet,
    `#F59E0B` amber, `#E6EDF3` text, plus a 24px grid and radial glows.
  - Removed the Google Fonts `<link>` tags entirely; fonts are injected through
    the new `{{FONT_CSS}}` token inside `<style>`.
  - Added `{{SOURCE}}`, `{{TIMESTAMP}}`, and `{{PAGE_LABEL}}` tokens.
- Added `RenderError` to `scripts/errors.py` (no duplicate class in the renderer).
- Rewrote `build_card_slides` in `render/cards.py`:
  - Removed all hardcoded slide copy, including `Engineering Implementation &
    Tradeoffs`, `Deterministic State Architecture`, and `Production Reliability
    Checklist`, plus the generic fallback bodies.
  - Slide roles are now `CONTEXT` -> `MECHANISM` -> `CHECKLIST` (or `CORE` for a
    single slide), derived from `headline`, `body`, `points`, and `takeaway`.
  - Each slide gets a role-derived `tag`, `panel_tag`, and `page_label`.
  - `source` is derived from `topic_data["url"]`/`source`; `timestamp` comes from
    the topic or a caller-supplied deterministic date (default UTC today).
  - `_validate_slides` rejects empty headline/body/bullets, duplicate bodies, and
    duplicate bullet sets with `RenderError("insufficient_slide_content")`.
- Made capture deterministic and offline in `render/cards.py`:
  - Vendored `Geist-Regular`, `Geist-SemiBold`, and `GeistMono-Regular` `.woff2`
    files under `render/assets/fonts/` (OFL-1.1, documented in a local README).
  - `_font_css()` base64-encodes them into `@font-face` rules with
    `font-display: block`; a missing font raises `RenderError`.
  - `_capture_card_png(..., scale=2.0)` renders `1080x1920` at 1x and
    `2160x3840` at 2x via `Emulation.setDeviceMetricsOverride` and a 9:16 clip.
  - Replaced `asyncio.sleep(1.2)` with a `document.fonts.ready` + image-decode +
    double-`requestAnimationFrame` wait, bounded to 10s, raising
    `RenderError("capture_not_ready")` on timeout.
  - Capture raises `RenderError` with the output path on CDP failure or an empty
    response/file, and only returns `True` after a non-empty PNG is written.
  - Removed the `except Exception: count = 2` fallback in `generate_topic_cards`;
    `determine_card_count` errors now surface.
- Removed the silent infocard fallback in `scripts/repurpose.py`:
  - `repurpose_topic` no longer catches card-generation errors or substitutes a
    16:9 infocard.
  - `RenderError` propagates so the draft is blocked.
  - Draft `media` entries are filtered to files that exist and are non-empty;
    an empty result raises `RenderError("no_renderable_media")`.
- Added `tests/test_storybook_render.py` with 8 tests: real 1x/2x pixel
  dimensions, 9:16 template + no remote fonts, topic differentiation and
  intra-set uniqueness, removal of the legacy headlines, thin-topic rejection,
  offline-embedded fonts with no remote URLs, absence of the fixed sleep, and
  `RenderError` propagation through `repurpose_topic`.
- Updated two tests that assumed the old behavior:
  - `tests/test_repurposer.py` no longer patches the removed `create_infocard`.
  - `tests/test_platform_limits.py` now returns a real PNG path instead of `[]`,
    because empty card output is now a hard failure.

## Verification

- `py -3.12 -m pytest tests/test_storybook_render.py -q` -> **8 passed**
- Full repository suite -> **289 passed, 3 warnings**
- `py -3.12 -m py_compile scripts/errors.py render/cards.py scripts/repurpose.py`
  -> **passing**
- `Select-String render/card_template.html -Pattern 'fonts.googleapis.com|fonts.gstatic.com'`
  -> **no matches**
- `rg -n "asyncio\.sleep\(1\.2\)|Engineering Implementation|Deterministic State Architecture|Production Reliability Checklist|Verified Reference" render/cards.py render/card_template.html`
  -> **no matches**
- `rg -n "infocard" scripts/repurpose.py` -> **no matches**
- `test_slide_dimensions` rendered through a real CDP browser and asserted
  `(1080, 1920)` at 1x and `(2160, 3840)` at 2x with PIL.

## Notes

- No live content was published.
- The three remaining warnings are the pre-existing mock-related
  `coroutine ... was never awaited` warnings, not failures.
- Fonts were fetched once at development time from `geist@1.3.1` and committed;
  the renderer itself makes no network calls.
- `scripts/pipeline.py` was intentionally not modified: it already lets unknown
  exceptions propagate, which blocks the draft as required by D-09.
- The pixel dimension test skips only when `CI` is set and no CDP browser is
  available; on a developer machine it always runs.
