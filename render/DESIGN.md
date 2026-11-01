# OmniPost Semantic Design Contract (`DESIGN.md`)

> **Contract Authority:** Enforces `/taste-design` and `/gpt-taste` standards across all OmniPost visual generation engines (`render/cards.py`, `render/card_template.html`, `render/carousel.py`, `render/template.html`).

---

## 1. Atmosphere & Aesthetic Intent

OmniPost graphics must look like artifacts produced inside a high-agency engineering studio—an architect sharing a terminal snippet, state machine blueprint, or benchmark diff from their workstation. 

We deliberately ban marketing fluff, generic AI card templates, vibrant neon glows, and gradient washes. Every visual component must communicate technical rigor, structural clarity, and high production craft.

---

## 2. Color System & Design Tokens

All colors are expressed as semantic CSS variables.

| Token | Variable | Value | Purpose |
|---|---|---|---|
| **Canvas Base** | `--bg-canvas` | `#090D16` (Deep Zinc-950 Slate) | The primary background. **Pure black (`#000000`) is banned.** |
| **Panel Surface** | `--bg-panel` | `#121824` | Elevated cards, diagram boxes, and code containers. |
| **Elevated Surface** | `--bg-panel-elevated` | `#182234` | Nested nodes, active code lines, and highlighted pills. |
| **Subtle Border** | `--border-subtle` | `rgba(255, 255, 255, 0.08)` | 1px clean separation lines between surfaces. |
| **Active Accent Border** | `--border-accent` | `rgba(0, 229, 153, 0.28)` | Precision 1px highlight for selected nodes and tags. |
| **Primary Text** | `--text-primary` | `#F1F5F9` (Slate-100) | High-contrast headlines and active code tokens. |
| **Secondary Text** | `--text-secondary` | `#94A3B8` (Slate-400) | Analytical descriptions and diagram labels. |
| **Muted Text** | `--text-muted` | `#64748B` (Slate-500) | Timestamps, line numbers, and pagination. |
| **Singular Accent** | `--accent-primary` | `#00E599` (Emerald) or `#38BDF8` (Cyan) | **Single accent only** (< 80% saturation). No dual gradients. |
| **Accent Soft** | `--accent-soft` | `rgba(0, 229, 153, 0.10)` | Subtle pill and badge fills. |

### Color Guardrails:
- **Rule 1 (Base):** Always Zinc-950 slate (`#090D16` / `#0D1117`). Never pure `#000000` void.
- **Rule 2 (Singular Accent):** Exactly **one** accent hue per render deck. Saturation strictly < 80%.
- **Rule 3 (Zero Neon):** Banned: `box-shadow: 0 0 18px var(--emerald)` and multi-color radial gradient sweeps (`radial-gradient(..., rgba(139, 92, 246, 0.16)...)`).

---

## 3. Typography & Typesetting

OmniPost uses 100% offline vendored font faces. Remote Google Fonts CDN links are strictly prohibited.

- **Display & Prose:** `Geist` (`400`, `600`)
  - Headlines: Track-tight (`letter-spacing: -0.035em`), weight `600`, line-height `1.12`. Max 3 lines.
  - Body: Weight `400`, line-height `1.5`, max width `65ch`.
- **Artifacts, Code & Badges:** `Geist Mono` (`400`, `500`, `600`)
  - Applied to node boxes, code lines, metrics, timestamps, and step indicators.
  - Letter-spacing: `+0.04em` on uppercase tags; `normal` on code.

---

## 4. Layout Architecture & Modular Widgets

### 9:16 Storybook Card Structure (1080 x 1920)

```
+-------------------------------------------------------------+
| Header Band (15% / ~288px)                                  |
| [OP] @Lordporus   [SYSTEMS ARCHITECTURE]          01 / 03   |
+-------------------------------------------------------------+
| Hero & Component Area (70% / ~1344px)                       |
|                                                             |
| 2-Line Punchy Engineering Headline                          |
|                                                             |
| +---------------------------------------------------------+ |
| | Modular Widget Slot:                                    | |
| | - Architecture Flow Panel ([A] -> [B] -> [C])           | |
| | - Terminal Code Panel (syntax-highlighted box)          | |
| | - 2-Column Comparison (Naive vs. Production)            | |
| | - 3-Point Actionable Checklist                          | |
| +---------------------------------------------------------+ |
|                                                             |
+-------------------------------------------------------------+
| Footer Band (15% / ~288px)                                  |
| arxiv.org • 2026-11-01                       OmniPost Eng   |
+-------------------------------------------------------------+
```

### 1:1 Document Carousel Structure (1080 x 1080)

1. **Slide 1 — The Hook:** Punchy claim + category tag + monospace badge.
2. **Slide 2 — The Problem Anatomy:** Highlighting the failure trap (Naive vs. Production fix).
3. **Slide 3 — The Architecture Flow:** Monospace node diagram showing system components and state transitions.
4. **Slide 4 — The Production Checklist:** 3 structured execution steps.

---

## 5. Visual Component Specifications

### 1. Architecture Flow Panel (`.arch-flow`)
- Container: Border `1px solid var(--border-subtle)`, background `var(--bg-panel)`, border-radius `16px`, padding `32px`.
- Nodes: Monospace boxes (`.arch-node`) with subtle elevated background `var(--bg-panel-elevated)`, border `1px solid var(--border-accent)`, border-radius `8px`, padding `16px 24px`.
- Connectors: Clean directional ASCII/SVG arrows (`->`, `==>`, `➔`) in `var(--accent-primary)`.

### 2. Terminal Code Panel (`.terminal-window`)
- Window Bar: Dark header with 3 subtle gray dots (`#334155`), terminal tab title in `Geist Mono`.
- Editor: Background `#0B0F17`, 1px border `var(--border-subtle)`.
- Line Numbers: Monospace, color `var(--text-muted)`.
- Syntax Tokens: Keyword (`var(--accent-primary)`), string (`#38BDF8`), function (`#E2E8F0`), comment (`#64748B`).

### 3. Tactile Checklist (`.checklist`)
- Monospace step indicators: `[01]`, `[02]`, `[03]` in `var(--accent-primary)`.
- Each item has a distinct bold title and a concise operational consequence.

---

## 6. Strict Anti-Patterns (Banned)

- ❌ **No Multi-Color Radial Washes:** Dual purple/green gradient backgrounds are banned.
- ❌ **No Glowing Neon Drops:** Box shadows with blur radius > 12px or opacity > 0.3 on colored borders.
- ❌ **No Generic AI Slogans:** Banned labels: `THE CONTEXT`, `SYSTEM // 2026`, `Production Principles to Remember`.
- ❌ **No Wall-of-Text Paragraphs:** Never render 8+ lines of unformatted academic abstracts.
- ❌ **No Remote Assets:** Zero network font or image calls during rendering.
