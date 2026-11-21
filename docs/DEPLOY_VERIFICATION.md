# Deploy Verification — 2026-11-10

Phase 20, Task 1 (`20-02-PLAN.md`). Docker Desktop on Windows, compose project `test-tweetytweet`.

## Source

- Branch: `main`
- Commit: `0a8ed93` (Merge PR #16)
- Includes PR #15 (`765a5de`) and PR #16 (`243f4fa`)

## Image and container

| Item | Value |
| :--- | :--- |
| Image | `test-tweetytweet-omnipost:latest` |
| Image ID | `sha256:0c13f3a221ae019168af4f195fc07f429c2a8e5e58176af8dd26baa9e3079e01` |
| Container | `omnipost-engine` |
| Status | `Up (healthy)` |
| Built at | 2026-11-10T19:28+05:30 |

## Source hash comparison

Host and container must match exactly.

| File | SHA-256 | Match |
| :--- | :--- | :--- |
| `scripts/validator.py` | `ab1ef643f70fafb187223ee85e16b7ef345bbda9c0bfdf95d206f0b958285ac5` | yes |
| `scripts/pipeline.py` | `5051fd628fd4530ec20f8fc8bc86bb53657ff37b4941e0fe245f135fa9c26af9` | yes |
| `scripts/publish_now.py` | `028667036129ab48fc3d906c399efa5f2db11ae81d8bdd436ed2184725d1f8f5` | yes |
| `scripts/due.py` | `67ad772d1f30ee01c3fbd3b215cd00a2875b61bee67ed586d0694acf060b20d7` | yes |

## Behaviour checks

| Check | Result |
| :--- | :--- |
| `validator` exposes `check_measured` | `True` |
| `pipeline` calls with `check_measured=False` | `True` |
| `publish_now` calls with `check_measured=False` | `True` |
| `due.py show` (read-only) | prints the active plan with per-platform status |

`due.py show` output confirms per-platform ledger rows are read correctly
(`X/BLUESKY/LINKEDIN/THREADS: published_verified` on the 20:00 slot).

**Not run:** `due.py check` — it increments the tick counter and can retire overdue slots.

## Account ceiling

- `max_chars: 280`
- `max_chars_verified: true`

The measured-ceiling gate stays on the scheduled path.

## Startup observation

The daemon started and immediately ran the daily pipeline for `2026-11-10`.
The merged guardrails are active: the 13:00 candidate was rejected with
`threads copy is only 325 units after fitting; minimum is 350`.

## Notes

- A local uncommitted edit to `adapters/linkedin.py` was stashed before the build
  and is **not** in this image.
- `config.json`, `state.json`, `drafts/`, `swipe/`, and `scratch/` are mounted from the host.
