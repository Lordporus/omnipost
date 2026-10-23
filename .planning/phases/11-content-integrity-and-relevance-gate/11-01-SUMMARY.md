# Phase 11 Plan 01 Summary

**Status:** Complete

**Branch:** `phase-11-content-integrity`

## What changed

- Added `scripts/errors.py` with `ContentError`, `TopicRejected`, `NoRelevantTopic`, and `DuplicateTopic`.
- Added `scripts/relevance.py` with deterministic `score_item` / `score_candidates`, engineering taxonomy scoring, whole-token blocklist matching, voice-profile alignment, and runtime defaults.
- Added the `content.relevance` block to `config.example.json`.
- Made generation fail closed in `scripts/generate.py`:
  - Removed the generic `"Analyzing architectural tradeoffs..."` summary fallback.
  - Removed `fallback_defaults` from `extract_key_takeaways`.
  - Added summary validation (`missing_summary`) and grounded-point extraction (`insufficient_takeaways`).
  - `generate_topic_from_items` now scores candidates, selects the highest-scoring accepted source, gates LLM output, gates the heuristic fallback, and rejects empty input.
  - Takeaways are always topic-derived; domain/source/`Verified Reference` takeaways are sanitized away.
- Removed the unconditional heuristic fallback from `scripts/llm.py`; failures now return `(False, None)`.
- Updated `scripts/pipeline.py`:
  - Loads the voice profile once per run and passes it to generation.
  - Retries over candidate items on `TopicRejected`.
  - Raises `NoRelevantTopic` with date/slot/rejection reasons when a slot is exhausted.
  - Rejects duplicate content with `DuplicateTopic` and persists `content_hash` on draft slots.
- Rewrote LinkedIn and Threads formatters in `scripts/repurpose.py`:
  - LinkedIn sections come from `body`, `points[:3]`, and `takeaway`.
  - Hardcoded bottleneck/production-principles/cards-below copy is gone.
  - CTA is media-aware and omitted when there is no media.
  - Threads uses the topic takeaway and never injects the old state-drift sentence.
  - Existing platform-native text is preserved when supplied.
- Added `tests/test_content_integrity.py` with the 13 Phase 11 regression tests.

## Verification

- `py -3.12 -m pytest tests/test_content_integrity.py -q` → **13 passed**
- Targeted regression run (`test_content_integrity`, `test_generate`, `test_llm`, `test_pipeline`, `test_repurposer`, `test_multiplatform_adaptation`) → **passing**
- `py -3.12 -m py_compile scripts/errors.py scripts/relevance.py scripts/generate.py scripts/llm.py scripts/pipeline.py scripts/repurpose.py` → **passing**
- `py -3.12 -c "import scripts.generate, scripts.repurpose, scripts.pipeline"` → **passing**
- Forbidden-string grep over `scripts/` → **no matches**
- Two-topic smoke test → different bullets and no domain takeaway

## Notes

- No live content was published.
- The full repository suite still contains pre-existing LinkedIn/Threads adapter failures unrelated to Phase 11; Phase 11's targeted content tests are green.
