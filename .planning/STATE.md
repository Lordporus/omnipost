# GSD State Memory

## Current Position
- Milestone: V2.0 Multi-Platform Syndicate
- Completed Phases: Phase 1 (Adapters & Bluesky), Phase 2 (Visual Pipeline), Phase 3 (LinkedIn CDP Adapter), Phase 4 (Meta Threads CDP Adapter & Content Repurposer)
- Active Phase: Phase 5 — Unified Ledger & Cross-Platform Engagement
- Status: Ready for planning

## Key Decisions
- Preserve working V1.0.1 X implementation unconditionally (`adapters/x.py` wraps `post.py`).
- Implement Bluesky natively via AT Protocol HTTP XRPC without browser overhead.
- Require UTF-8 byte slice calculation for Bluesky RichText facets.
- Use CDP `Page.printToPDF` for carousels to avoid C-library dependencies.
- Use environment variables (`app_password_env`, `token_env`) for secrets in `config.json`.
- Isolate platform failures in `state.json` v2.0 to prevent duplicate posting.
- Use 100% CDP Browser Automation for Meta Threads (`adapters/threads.py`) to bypass public image hosting constraints ($0 cost, local file attachments).
- Use polymorphic draft structure (`platforms` dictionary in draft JSON) with backward-compatible fallback to single `text`.

## Blockers
- None.
