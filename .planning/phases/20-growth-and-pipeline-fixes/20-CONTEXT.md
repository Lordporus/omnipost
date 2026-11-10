# Phase 20 Context: Growth & Pipeline Fixes (Post-Merge)

**Source**: `GROWTH_AND_PIPELINE_FIX_PLAN.md`
**Created**: 2026-11-09
**Predecessor**: Phase 19 (complete)

## Scope

Finish the items in `GROWTH_AND_PIPELINE_FIX_PLAN.md` that PR #15 did not close. No new features, no prompt rewrites beyond one editorial rule, no platform adapter changes.

## Closed by PR #15 — do NOT re-implement

PR #15 was merged into `main` as `765a5de`.

| Plan item | Commit | What shipped |
| :--- | :--- | :--- |
| **Defect 1** — `publish_now.py` bypass | `5e97b3f` | Fitted text is validated before dispatch; blocked platforms record `failed` and alert. |
| **Defect 2** — `due.py` validates X only / false-positive X limit | `5e97b3f` | Every platform in the slot is validated with its own copy and limits; disabled copies are skipped. |
| **Defect 4** — branch divergence | `765a5de` | The work is on `main`; `feat/humanized-posts` merged. |
| **Defect 5** — `pipeline.py` never validates | `5e97b3f` | `_draft_violations` / `_guardrail_violations` / `_drop_slot` run full guardrails at generation. |
| **Defect 6** — silent drop | `5e97b3f` | `guardrail_blocked` + one `guardrail_drop` webhook per slot, deduped by `guardrail_alerted`. |
| **CI fallout** | `6d7007e` | `check_measured` flag keeps the account-readiness gate on `due.py` only; generation and manual dispatch validate content. |

Verified local suite after the merge: **451 passed**. CI: all six Test jobs green (ubuntu/windows × Python 3.10/3.11/3.12).

## Remaining scope (this phase)

### 20-01 — code, autonomous
1. **Defect 3 audit**: the RSS and HN collectors already call `sanitize_feed_text`, but the raw text is not sanitized when an item is *loaded* from `swipe/*.json`, and the historical files still contain raw markers. A repo-local grep on 2026-11-09 found 9–24 marker lines (`arXiv:`, `Announce Type`, `Article URL`) in each of the seven files from `2026-10-25` through `2026-11-01`. Generation reads those files, so a stale bank can still feed raw metadata into the prompt; the guardrail then drops the slot instead of the item. Fix at the boundary, then audit/clean the files.
2. **§5 template**: `build_system_prompt` bans engagement bait and AI tells but never states the shape that worked: *tension → real entity → engineering axiom*. Add one editorial rule, not a rewrite.

### 20-02 — operator checkpoints, non-autonomous
1. **Deploy**: the running container was built from uncommitted code on 2026-10-30. The merge makes `main` correct; the container is not. Rebuild, then prove the merged code is inside it.
2. **LinkedIn §2.5**: 690 followers, 0.038 reach. Diagnose before scheduling anything else on LinkedIn.
3. **Manual §4 / §6**: profile copy and the 10-comments/day protocol are account work, not code.

## Decisions

- Keep the measured-ceiling gate on the scheduled path (`due.py`). Generation validates content only.
- Sanitize at the load boundary rather than only at collection: it fixes both new collections and existing swipe files with one function.
- Do not delete historical swipe files; clean them in place so the audit stays reproducible.
- Defect 3 is hygiene, not a confirmed live defect: no evidence the current RSS path leaks.

## Out of scope

- Profile edits, LinkedIn diagnosis automation, or any live posting run performed by an agent.
- Rewriting the generation prompt schema or the platform adapters.
- `launch_chrome.bat` and `scripts/launch_desktop_chrome.py` (personal paths, duplicate `ensure_chrome`).
