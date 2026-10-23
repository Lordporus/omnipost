# Phase 11: Content Integrity & Relevance Gate - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase fixes the content engine only: research item selection, topic synthesis, takeaways, and platform copy generation. It does **not** change adapters, state semantics, character-limit counting, or the renderer; those are Phases 12–15.

The source of truth is `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.1–6.3 and §7. The live evidence is `drafts/2026-10-23.json`.

</domain>

<decisions>
## Implementation Decisions

### Relevance gate
- **D-01:** Add a deterministic relevance gate before generation. Score each item against an AI/engineering taxonomy plus a blocklist and a minimum score; no network call and no LLM dependency is required for the gate.
- **D-02:** Political, financial, celebrity, and general-news headlines must be rejected. A rejected item is dropped and the pipeline tries the next candidate; if no candidate passes, the draft fails with an actionable error instead of inventing a topic.
- **D-03:** Thresholds and blocklist entries are configurable under a new `content` block in `config.json`, with safe defaults committed in `config.example.json`.

### Fail-closed synthesis
- **D-04:** An item without a usable summary (missing, title-only, or under 40 characters) is not templated into `"Analyzing architectural tradeoffs... for {title}"`. It is requeued or skipped.
- **D-05:** Remove the `fallback_defaults` list. If fewer than three topic-grounded points can be extracted, the item is rejected rather than padded with generic engineering slogans.
- **D-06:** Takeaways come from the topic's own final insight or an explicit source takeaway. A domain name, `"Verified Reference"`, or an unrelated slogan is never a takeaway.

### Copy integrity
- **D-07:** Remove the hardcoded LinkedIn "Architectural Bottleneck", "Production Principles", and "cards below" paragraphs. Every section is derived from the topic's body/points.
- **D-08:** Replace `"Why {headline} Matters in Production"` with a grammar-safe headline treatment that works for noun phrases and sentence-style titles.
- **D-09:** Enforce cross-slot uniqueness: no two slots in the same day may share a bullet set or identical post text. A content hash is stored with the draft for comparison.

### Claude's Discretion
- Exact taxonomy terms, score weights, and the blocklist starter set.
- Whether relevance scoring lives in `scripts/relevance.py` or `scripts/generate.py`; a separate module is preferred for testability.

</decisions>

<specifics>
## Specific Ideas

- The gate must reject the three observed bad examples: `"Jared Kushner Hacked Phone Reveals Secret Negotiations, Millions in Transactions"`, `"Docker is weird"`, and `"Wine ported to OpenBSD"` unless a real engineering summary justifies them.
- The LinkedIn output must never contain the literal strings `"The Architectural Bottleneck:"`, `"Production Principles to Remember:"`, or `"Review the visual system breakdown cards below"`.
- Threads must never contain `"codeandcake.dev • Verified Reference"`.

</specifics>

<canonical_refs>
## Canonical References

### Overhaul diagnosis
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.1 — off-topic HN headlines reach publication.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.2 — fallback synthesis and domain takeaway.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §6.3 — hardcoded LinkedIn boilerplate.
- `OMNIPOST_SYSTEM_OVERHAUL_BRAINSTORMING.md` §7 — fix order and acceptance criteria.

### Existing implementation
- `scripts/research.py` — research collection and item shape.
- `scripts/generate.py` — `extract_key_takeaways`, `generate_topic_from_items`, `determine_card_count`.
- `scripts/repurpose.py` — platform formatters.
- `scripts/pipeline.py` — daily orchestration.
- `drafts/2026-10-23.json` — live evidence of the failure.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `extract_key_takeaways` already deduplicates and excludes title echoes; it can be kept as the extraction primitive after the fallback list is removed.
- `generate_topic_from_items` already returns a structured topic dict consumed by `repurpose_topic`; preserve that contract.
- `config.json` already has platform and browser blocks; add `content` alongside them.

### Established Patterns
- The pipeline imports `generate` and `repurpose` directly and writes `drafts/YYYY-MM-DD.json`; rejection must surface as a controlled exception that the pipeline handles.
- Tests are pytest-based and currently mock external calls; relevance and synthesis tests should be pure functions with no browser/network.

### Integration Points
- `scripts/pipeline.py` calls `generate_topic_from_items` per slot.
- `scripts/repurpose.py` consumes `headline`, `body`, `points`, `takeaway`, and `category`.
- `scripts/publish_now.py --fresh` also calls the same generation path and must receive the same fail-closed behavior.

</code_context>

<deferred>
## Deferred Ideas

- Semantic embeddings or LLM-based relevance scoring (a deterministic gate is sufficient for this phase).
- Voice-profile-driven rewriting beyond relevance/uniqueness.
- Adapter and renderer fixes — Phases 13–15.

</deferred>

---

*Phase: 11-content-integrity-and-relevance-gate*
*Context gathered: 2026-10-23*
