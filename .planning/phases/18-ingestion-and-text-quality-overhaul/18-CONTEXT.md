# Phase 18: Ingestion & Text Quality Overhaul - Context

**Gathered:** 2026-11-01  
**Status:** Ready for planning  
**Source Specification:** `humanized_quality_and_taste_plan.md`  

<domain>
## Phase Boundary

This phase hardens the content pipeline against raw scraper metadata leakage, repetitive cross-section copy, and mid-word text truncation. It touches:
1. Feed ingestion boundary in `scripts/research.py`.
2. Cross-platform polymorphic copy synthesis in `scripts/repurpose.py`.
3. Word-boundary safe character fitting in `scripts/platform_limits.py`.
4. Humanity gate enforcement in `scripts/validator.py` and negative prompt guidance in `scripts/llm.py`.

It does **not** overhaul visual card rendering or carousels; those are isolated to Phase 19.
</domain>

<decisions>
## Implementation Decisions

### Feed Boundary Sanitization
- **D-01:** Implement `sanitize_feed_text(raw: str) -> str` in `scripts/research.py` that strips HTML entities, arXiv announcement prefixes (`arXiv:\d+\.\d+(v\d+)?(\s*\[[\w\.\-]+\])?\s*(Announce Type:\s*[\w\-]+\s*)?(Abstract:\s*)?`), Hacker News link metadata tails (`(Article URL|Comments URL|Points):\s*\S+.*$`), and CMS syndication signatures.
- **D-02:** Apply `sanitize_feed_text()` uniformly inside `rss()` and `hn()` at collection time so that `swipe/YYYY-MM-DD.json` contains pristine summaries before LLM or fallback synthesis consumes them.

### Copy Deduplication & Dynamic Formatting
- **D-03:** Refactor `format_linkedin()` in `scripts/repurpose.py` to measure sentence overlap via token Jaccard similarity. If `points[0]` overlaps >60% with `body`, discard `points[0]` and shift to subsequent points.
- **D-04:** If `takeaway` duplicates `points[-1]`, derive a distinct actionable synthesis rather than repeating the sentence verbatim.
- **D-05:** Replace static boilerplate headers (`"What changes in practice:"`, `"Bottom line:"`) with dynamic semantic connectors.
- **D-06:** Refactor `format_threads()` to remove redundant bullet repeats when `clean_body` already contains the insight. Remove the hardcoded `"What architectural tradeoffs have you seen in your stack?"` prompt question, defaulting to punchy declarative observations.

### Word-Boundary Safe Limits
- **D-07:** Refactor `fit()` and `truncate_words()` in `scripts/platform_limits.py` to strictly preserve word boundaries. Never slice mid-token (e.g. `cont`, `sho`).
- **D-08:** Strip trailing conjunctions, prepositions, and orphan punctuation (`and`, `or`, `with`, `for`, `to`, `in`, `on`, `,`, `;`, `:`, `-`, `•`) before appending clean ellipsis (`...`).

### Humanity Guardrails & Prompts
- **D-09:** Add Check #9 to `validate_draft_guardrails()` in `scripts/validator.py`: reject any draft containing raw scraper metadata markers (`arXiv:`, `Announce Type:`, `Abstract:`, `Article URL:`) or trailing broken conjunctions.
- **D-10:** Update `scripts/llm.py` (`build_system_prompt()`) with explicit negative constraints banning feed prefix echoing and self-duplication. Update `references/voice-samples.md` with winning examples demonstrating this standard.
</decisions>

<canonical_refs>
## Canonical References
- `humanized_quality_and_taste_plan.md` §5 (Proposed Changes - Components 1, 2, 3, 4)
- `scripts/research.py` — `strip_html()`, `rss()`, `hn()`
- `scripts/repurpose.py` — `format_linkedin()`, `format_threads()`
- `scripts/platform_limits.py` — `truncate_words()`, `fit()`
- `scripts/validator.py` — `score_humanity()`, `validate_draft_guardrails()`
- `scripts/llm.py` — `build_system_prompt()`
- `references/voice-samples.md` — Measured operator voice examples
</canonical_refs>

<code_context>
## Existing Code Insights
- `scripts/research.py:153`: `summary = strip_html(child.text or "")[:400]` is where raw arXiv announcement prefixes leak into swipe items.
- `scripts/repurpose.py:78-85`: Concatenates `clean_body`, `"What changes in practice:"`, `clean_points`, and `"Bottom line: " + clean_tk` without similarity checks.
- `scripts/repurpose.py:116-123`: Appends hardcoded CTA `"What architectural tradeoffs have you seen in your stack?"`.
- `scripts/platform_limits.py:207-216`: Slices at word boundary but leaves trailing conjunctions (`...blockchain and...`).
- `scripts/validator.py:652-750`: Guardrails checks 1-8 are active; check 8 is humanity score. Check 9 will enforce metadata/dangling-word purity.
</code_context>

<deferred>
## Deferred Items
- Visual card layout, color palette overhaul, and PDF carousel re-architecture are handled in Phase 19.
</deferred>
