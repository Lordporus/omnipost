# Phase 14: Platform Copy Calibration & Media Contract - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase owns platform copy limits, truncation, minimum-length validation, and the image-vs-PDF media contract. It does **not** change content relevance (Phase 11), state semantics (Phase 12), or the visual design (Phase 15).

Source of truth: `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §2, §6.11–6.12, and §7.

</domain>

<decisions>
## Implementation Decisions

### Counting and limits
- **D-01:** Create one `scripts/platform_limits.py` module with per-platform min/max and counting functions.
- **D-02:** X uses weighted character counting (CJK and emoji count as 2 where X does), Bluesky uses grapheme counting, Threads and LinkedIn use Unicode code points.
- **D-03:** The formatters must land inside the documented ranges: X 220–275, Bluesky 240–295, Threads 350–480 (never over 500), LinkedIn 1,500–2,500 when the source supports it (hard ceiling 3,000).
- **D-04:** Truncation happens on word boundaries with an ellipsis. No formatter may slice a word in half.
- **D-05:** If the source cannot meet the minimum, raise `CopyValidationError` and let the pipeline reject or requeue the topic; do not publish an undersized post silently.

### Media contract
- **D-06:** `repurpose_topic` must emit an explicit `media_type` per platform. `"image"` means the rendered PNG cards; `"carousel"` means a PDF document.
- **D-07:** LinkedIn sends a PDF only when `media_type == "carousel"` and no images are attached; otherwise it sends images. The capability flag and documentation must match the actual behavior.
- **D-08:** Wire `render/carousel.py` into the carousel path or remove `supports_pdf_carousel` and the `document_title` claim. Do not leave a dead capability.
- **D-09:** `publish_now` must not silently trim text; it validates with the shared limit utility and fails the platform with a clear error if the payload is invalid.

### Claude's Discretion
- Exact weighted-count implementation for X (range tables vs a small lookup).
- Grapheme counting approach (stdlib approximation acceptable; document the limitation).

</decisions>

<specifics>
## Specific Ideas

- The Threads overflow branch currently produces ~505 characters; it must be redesigned so the CTA fits inside 500.
- A 2,000-character LinkedIn body must not be cut at `text[:2950]` mid-sentence; it should be composed to fit or truncated at a sentence/word boundary.
- Emoji and CJK fixtures must be part of the limit tests.

</specifics>

<canonical_refs>
## Canonical References

- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §2 — platform calibration table.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.11 — Threads overflow and mid-word truncation.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.12 — dead PDF carousel.
- `scripts/repurpose.py`, `scripts/publish_now.py`, `adapters/linkedin.py`, `render/carousel.py`.
- `tests/test_repurposer.py`, `tests/test_multiplatform_adaptation.py`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PlatformCapabilities` already carries `max_characters`, `max_images`, and `supports_pdf_carousel`; use it as the single source for limits where possible.
- `repurpose_topic` already builds a per-platform dict with `media`, `media_type`, and `document_title`; preserve the shape.
- LinkedIn `_attach_document` and `_attach_images` already exist; the fix is in the selection logic, not a rewrite.

### Established Patterns
- Formatters are pure functions taking `headline`, `body`, `points`, `takeaway`; keep them pure and testable.
- `publish_now` applies a final `post_text[:max-3] + "..."` guard; replace it with validation.

### Integration Points
- `scripts/repurpose.py` feeds `drafts/YYYY-MM-DD.json`.
- `publish_now` reads `platforms.<name>.media_type` and passes it to `PublishPayload`.
- `adapters/linkedin.py` decides document vs image from `media_type` and paths.

</code_context>

<deferred>
## Deferred Ideas

- Per-platform LLM rewriting to hit exact lengths (deterministic composition is sufficient).
- Additional platforms beyond X, Bluesky, LinkedIn, Threads.
- Carousel design changes — Phase 15.

</deferred>

---

*Phase: 14-platform-copy-calibration-and-media-contract*
*Context gathered: 2026-10-23*
