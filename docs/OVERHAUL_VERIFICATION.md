# OmniPost Overhaul Verification

- Generated: `2026-10-24T14:52:41.625392+00:00`
- Git commit: `5a1caea`
- Source: **dry-run**
- Overall: **PASS**

> **Live evidence pending.** This report was generated from the
> deterministic dry-run. It does not claim a live post. An operator
> must run `python scripts/verify_overhaul.py --live --confirm-live
> --slot HH:MM` with real credentials and regenerate this file with
> `--source live`.

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| relevance | PASS | political rejected (blocklist:election, blocklist:president, blocklist:kushner); postgres accepted (score=8) |
| fail_closed_synthesis | PASS | title-only item raised TopicRejected: missing_summary: Postgres latency |
| uniqueness | PASS | distinct bullets/takeaways/fingerprints; repeated fingerprint detected |
| state_truth | PASS | unverified -> submitted_unverified (not done); verified -> published_verified (done) |
| limits | PASS | x=254, bluesky=255, threads=472, linkedin=1689; emoji/CJK fixtures pass |
| media_contract | PASS | image: no document title; carousel: PDF + media_type=carousel + title |
| duplicate_safety | PASS | repeated key skipped; pending timeout reservation blocks duplicate dispatch |
| two_topic | PASS | bullets, takeaways, platform copy, and slide headlines differ; slide plans are 9:16-shaped and font-independent |

## Per-platform evidence

| Platform | Status | Verified | URL | Content hash | Chars / limit | Assets | Dimensions | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| x | dry-run | False | - | `794bef323ad17a41` | 254 / 220-275 | 3 | 1080x1920 | - |
| bluesky | dry-run | False | - | `60dbd43dc2d455d9` | 255 / 240-295 | 3 | 1080x1920 | - |
| threads | dry-run | False | - | `d2caa0721f9731dc` | 472 / 350-480 | 3 | 1080x1920 | - |
| linkedin | dry-run | False | - | `769d83930140cc79` | 1689 / 1500-2500 | 3 | 1080x1920 | - |

## Content

- Source title: Postgres replication lag spikes under distributed write load
- Relevance score: 8
- Bullet count: 3
- Takeaway: batched acknowledgements
- Duplicate check: distinct A/B fingerprints; repeated fingerprint detected

## Visual

- Dimensions: 1080x1920 / 2160x3840 contract (render not requested)
- Font embedding: 3 embedded WOFF2 faces
- Offline render: not requested (--render)

## Duplicate safety

- Rerun: skipped (idempotency key reserved)
- Timeout reconciliation: pending reservation blocks duplicate dispatch

## Legend

- `PASS` - the check or platform is verified.
- `UNVERIFIED` - submitted but read-back did not confirm the post.
- `FAIL` - the check or platform failed.
- `dry-run` - deterministic offline evidence; not a live post.

## Overall verdict

**PASS**
