# Phase 14 Plan 01 Summary

**Status:** Complete

**Branch:** `phase-11-content-integrity` (Phase 14 implemented on the existing branch)

## What changed

- Added the shared limit engine in `scripts/platform_limits.py`:
  - `LIMITS` owns the target ranges: X `220-275` weighted (`hard_max=280`), Bluesky `240-295` graphemes (`300`), Threads `350-480` (`500`), LinkedIn `1,500-2,500` (`3,000`).
  - `count_x_weighted` counts ASCII/URLs as 1, CJK ranges and emoji as 2, and ignores combining marks, variation selectors, ZWJ, and emoji modifiers.
  - `count_graphemes` is a stdlib approximation covering combining marks, ZWJ sequences, emoji modifiers, keycaps, and regional-indicator flags.
  - `count_chars` counts Unicode code points for Threads and LinkedIn.
  - `truncate_words` measures with the platform counter, reserves ellipsis space, and never splits a whitespace-delimited token or URL.
  - `validate` raises below the minimum or above `hard_max`.
  - `fit` truncates to the target maximum and raises instead of padding when the result is below the minimum.
- Added typed errors in `scripts/errors.py`:
  - `CopyValidationError(ContentError)` carries `platform`, `count`, `limits`, and structured context.
  - `MediaContractError(AdapterError)` defaults to `stage="media_contract"`.
- Refactored all formatters in `scripts/repurpose.py`:
  - `format_x` builds headline plus up to three bullets and calls `fit("x", ...)`.
  - `format_bluesky` builds headline plus up to three numbered points and calls `fit("bluesky", ...)`.
  - `format_threads` composes headline/body/points/takeaway, reserves room for the CTA inside the target maximum, and always ends with the CTA question.
  - `format_linkedin` composes from topic-derived body/points/takeaway and calls `fit("linkedin", ...)`.
  - Removed the old `text[:292]` and `text[:2950]` slices.
  - Native copy is preserved only when it already meets the platform contract; otherwise the formatter rebuilds it.
- Made the LinkedIn media contract explicit:
  - X, Bluesky, and Threads always emit `media_type="image"`.
  - LinkedIn emits `media_type="carousel"` only after `create_carousel_pdf` returns a `.pdf` path; otherwise it emits `"image"`.
  - Image payloads omit `document_title`; carousel payloads include it.
  - Carousel payloads contain only the PDF path, not the generated PNG cards.
  - A carousel request with media generation disabled, no slides, or no PDF path raises `MediaContractError`.
- Added `_select_linkedin_media` in `adapters/linkedin.py`:
  - Images win whenever image paths are attached.
  - Document mode is selected only for `media_type="carousel"` with a `.pdf` path and no images.
  - A carousel request without a PDF raises `MediaContractError`.
  - An image payload containing a PDF raises `MediaContractError` rather than silently ignoring the PDF.
- Changed dispatch in `scripts/publish_now.py`:
  - Known platforms are measured with `count_for`.
  - Oversized copy is word-boundary fitted to the target maximum and logs the before/after counts.
  - Undersized copy records a failed `PublishResult` with `CopyValidationError` and does not dispatch.
  - Dry-run and live output print the measured count and platform target.
  - Removed the `post_text[: ...]` trim and the `payload.text[:80]` slice.
- Added `CopyValidationError` requeue handling in `scripts/pipeline.py`: a rejected candidate is dropped and the next candidate is tried, mirroring the `TopicRejected` path.
- Made `scripts/llm.py` tolerant of `CopyValidationError` when filling missing platform fields, leaving them empty for the pipeline requeue path.
- Added `tests/copy_fixtures.py` with rich, reusable topic and native-copy fixtures.
- Added `tests/test_platform_limits.py` with 12 tests covering weighted/grapheme counting, Threads CTA overflow, word-boundary truncation, X minimums, LinkedIn ranges, dispatch rejection and fitting, carousel/image contracts, pipeline requeue, and hardcoded-slice removal.
- Updated existing short-fixture tests to the new minimum-length contract instead of weakening the limits.

## Verification

- `py -3.12 -m pytest tests/test_platform_limits.py -q` → **12 passed**
- Targeted formatter/media suite (`test_platform_limits`, `test_repurposer`, `test_multiplatform_adaptation`) → **22 passed**
- Full repository suite → **281 passed, 3 warnings**
- `py -3.12 -m py_compile` over all changed modules → **passing**
- `rg -n "text\[:" scripts/repurpose.py scripts/publish_now.py` → **no matches**
- `rg -n "post_text\[:" scripts/publish_now.py` → **no matches**
- `CopyValidationError` subclasses `ContentError`; `MediaContractError` subclasses `AdapterError`.
- Direct limit checks:
  - `count_for('x', 'hello') == 5`
  - `truncate_words('one two three four', 12, 'x') == 'one two...'`
  - CJK/emoji and grapheme fixtures pass.

## Notes

- No live content was published.
- The remaining three warnings are pre-existing mock-related `coroutine ... was never awaited` warnings, not failures.
- Phase 14 was implemented on the existing feature branch after Phase 13; nothing was merged or pushed.
