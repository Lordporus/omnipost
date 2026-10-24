# Phase 15: 9:16 Storybook Renderer & Deterministic Assets - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase owns the HTML/CSS card template, the CDP screenshot pipeline, slide derivation, and font/asset determinism. It does **not** change content relevance (Phase 11), publishing state (Phase 12), or adapters (Phase 13).

Source of truth: `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §1, §4, §6.13–6.14, and §7.

</domain>

<decisions>
## Implementation Decisions

### Dimensions and layout
- **D-01:** The card canvas is 1080×1920 CSS pixels at 1x and 2160×3840 at 2x device scale. Update the template, viewport override, and screenshot clip together.
- **D-02:** The template uses the required storybook hierarchy: header band ~15% (badge, handle, category pill, pagination), hero ~50% (headline plus diagram/comparison), footer ~10% (source, verified domain, timestamp).
- **D-03:** Use the living palette (`#0D1117` canvas, emerald `#00E599`, violet `#8B5CF6`, amber `#F59E0B`) with subtle grid geometry and no empty voids.

### Slide content
- **D-04:** Every slide's headline, body, and bullets are derived from the topic. Remove the hardcoded "Engineering Implementation & Tradeoffs", "Deterministic State Architecture", and "Production Reliability Checklist" content.
- **D-05:** The slide plan is problem → mechanism → evidence → checklist, with 1–3 slides based on content depth. Each slide must have a non-empty body and at least one meaningful bullet.
- **D-06:** Long content must be reflowed or split; it must not overflow the 9:16 canvas.

### Determinism and failure
- **D-07:** Embed or vendor Geist/Geist Mono (local `@font-face`); remove the Google Fonts network dependency.
- **D-08:** Wait for `document.fonts.ready` and image decode before capture; remove the fixed 1.2-second sleep.
- **D-09:** A render failure raises `RenderError` and blocks the draft. No silent fallback to infocard or text-only publishing.
- **D-10:** The renderer must work offline and produce deterministic dimensions/content for the same input.

### Claude's Discretion
- Whether fonts are base64-embedded in the HTML or served from a local file path.
- Exact grid/diagram treatment per slide type.

</decisions>

<specifics>
## Specific Ideas

- The live card repeated `"Analyzing architectural tradeoffs... for Docker is weird..."`; the new renderer must show topic-specific content on every slide.
- Card 1 is the hook, card 2 is the mechanism, card 3 is the checklist; none may reuse another slide's body.
- The footer must show the real source domain and timestamp, not `"Verified Reference"`.

</specifics>

<canonical_refs>
## Canonical References

- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §1 — 1:1 vs 9:16, dead design.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §4 — storybook hierarchy and palette.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.13 — hardcoded slides 2–3.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.14 — non-deterministic rendering.
- `render/cards.py`, `render/card_template.html`, `render/carousel.py`, `scripts/repurpose.py`.
- `tests/test_carousel_rendering.py`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_card_slides` already accepts `topic_data`, `count`, and `author`; rewrite its slide derivation but keep the function contract.
- `render_card_html` already performs template token replacement; extend the tokens for header/footer/pagination.
- `_capture_card_png` already uses CDP `Emulation.setDeviceMetricsOverride` and `Page.captureScreenshot`; change dimensions and add readiness checks.
- `generate.determine_card_count` already selects 1–3; keep it as the density input.

### Established Patterns
- Cards are written to `scratch/cards/card_<date>_<slot>_card_<n>.png` and referenced from draft JSON.
- `repurpose_topic` catches card errors and falls back to infocard; this phase removes that silent fallback.

### Integration Points
- `scripts/repurpose.py` calls `generate_topic_cards`.
- `publish_now` attaches the resulting paths.
- Adapter `max_images` limits determine how many cards are sent per platform.

</code_context>

<deferred>
## Deferred Ideas

- Animated/video cards.
- AI-generated illustrations or diagrams.
- Per-platform visual variants (the requirement is one unified 9:16 set).

</deferred>

---

*Phase: 15-storybook-renderer-and-deterministic-assets*
*Context gathered: 2026-10-23*
