# Phase 19: Visual Taste-Design Architecture - Context

**Gathered:** 2026-11-01  
**Status:** Ready for planning  
**Source Specification:** `humanized_quality_and_taste_plan.md`  

<domain>
## Phase Boundary

This phase elevates OmniPost's visual presentation from generic AI card templates to high-agency, viral `/taste-design` standards. It touches:
1. `render/DESIGN.md`: The formal semantic design contract for typography, palette, geometry, and component layout.
2. `render/card_template.html` and `render/cards.py`: The 9:16 retina storybook PNG generator (1080x1920).
3. `render/template.html` and `render/carousel.py`: The 1080x1080 multi-slide PDF document carousel generator.

It does **not** modify ingestion scrapers or platform adapters; those boundaries were hardened in earlier phases.
</domain>

<decisions>
## Implementation Decisions

### Semantic Design System (`render/DESIGN.md`)
- **D-01:** Establish an unyielding design contract enforcing `/taste-design` standards:
  - Base: Deep Slate (`#090D16` / `#0D1117`), never pure black (`#000000`).
  - Surface: Elevated Technical Panel (`#121824`).
  - Border: 1px subtle line (`rgba(255, 255, 255, 0.08)`).
  - Accent: Maximum 1 singular accent with saturation < 80% (`#00E599` emerald or `#38BDF8` cyan).
  - Zero neon drop-shadow glows or multi-hue radial gradient washes.
  - Monospace engineering badges (`[ARCHITECTURE]`, `[BENCHMARK]`) instead of pulsing glowing dots.

### 9:16 Storybook Card Engine
- **D-02:** Overhaul `render/card_template.html` and `render/cards.py`:
  - Strip the multi-colored radial gradient wash (`radial-gradient(..., rgba(139, 92, 246, 0.16)...)`).
  - Remove `.brand-dot` with `box-shadow: 0 0 18px var(--emerald)`.
  - Replace the single giant paragraph dump with modular visual builders:
    - **Architecture Flow Widget**: Monospace boxed component flow (`[Client] -> [Gateway] -> [DB]`).
    - **Terminal Code Widget**: Syntax-highlighted code panel with line numbers and subtle dark background.
    - **Tactile Metrics Box**: Clean, 1px-bordered comparison or key metric callouts.
  - Strip footer boilerplate (`omnipost.local`, `2026-10-31`, `CONTEXT`).
  - Retain 100% offline rendering with embedded base64 WOFF2 Geist & Geist Mono fonts.

### 1080x1080 PDF Carousel Engine
- **D-03:** Overhaul `render/template.html` and `render/carousel.py`:
  - Remove remote Google Fonts `<link>` tags; inject vendored base64 Geist fonts directly into `<style>`.
  - Enforce a 4-slide viral engineering narrative:
    - Slide 1: Hook + Asymmetric Visual Callout.
    - Slide 2: Problem Anatomy / 2-Column Comparison.
    - Slide 3: Architecture Flow Diagram or Terminal Code Box.
    - Slide 4: 3-Point Actionable Production Checklist.
  - Ban duplicate copy across slides (every slide derives a distinct angle from the topic).
  - Remove multi-color gradient accents (`--accent-gradient`), unifying around the singular precision accent token.
</decisions>

<canonical_refs>
## Canonical References
- `humanized_quality_and_taste_plan.md` §4 (Current vs. Target Viral Standard) & §5 (Component 5)
- `render/card_template.html` — Storybook template
- `render/cards.py` — Storybook renderer & slide builder
- `render/template.html` — Carousel HTML template
- `render/carousel.py` — Carousel builder & CDP PDF print driver
- `render/assets/fonts/` — Vendored Geist and Geist Mono WOFF2 font files
</canonical_refs>

<code_context>
## Existing Code Insights
- `render/card_template.html:50-54`: Defines the radial gradient background with purple/green glows.
- `render/card_template.html:93`: Defines the neon pulsing `.brand-dot`.
- `render/template.html:6-8`: Connects to `https://fonts.googleapis.com` (external dependency).
- `render/cards.py:69-74`: Hardcodes role metadata with generic tags (`THE CONTEXT`, `omnipost.local`).
- `render/cards.py:184-240`: `build_card_slides()` creates generic text-only slides instead of architecture/code widgets.
</code_context>

<deferred>
## Deferred Items
- Interactive web widgets or dynamic video generation (covered in future milestones).
</deferred>
