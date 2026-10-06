# Requirements: OmniPost V2 Multi-Platform Expansion

## Functional Requirements

### Phase 1: Adapter Foundation & Bluesky Integration
- [x] **REQ-ADAPT-01:** Abstract base class `PlatformAdapter` with standard contracts (`check_session`, `publish`, `verify`, `capabilities`).
- [x] **REQ-ADAPT-02:** Dataclass contracts (`PlatformCapabilities`, `PublishPayload`, `PublishResult`) defined with typing.
- [x] **REQ-X-01:** Extract monolithic `post.py` publishing logic into clean `adapters/x.py` implementing `PlatformAdapter`.
- [x] **REQ-BSKY-01:** Implement `adapters/bluesky.py` using AT Protocol XRPC REST calls (`com.atproto.server.createSession`, `com.atproto.repo.uploadBlob`, `com.atproto.repo.createRecord`).
- [x] **REQ-BSKY-02:** Parse and calculate UTF-8 byte slice indices for `app.bsky.richtext.facet` on URLs and @mentions.
- [x] **REQ-CFG-01:** Update `config.json` schema to support per-platform toggle blocks (`platforms.x`, `platforms.bluesky`).
- [x] **REQ-TEST-01:** Unit tests for adapter contracts, Bluesky facet calculations, and mock XRPC payloads.

### Phase 2: Zero-Dependency Visual Pipeline
- [x] **REQ-VIS-01:** Implement `render/infocard.py` producing dark-mode 16:9 PNG cards (1200x675) with Pillow.
- [x] **REQ-VIS-02:** Implement `render/carousel.py` producing 1080x1080 multi-page PDF carousels via HTML + CDP `Page.printToPDF`.
- [x] **REQ-VIS-03:** Support media attachments in `PublishPayload` for both X and Bluesky.

### Phase 3: LinkedIn CDP Adapter
- [x] **REQ-LINK-01:** Implement `adapters/linkedin.py` driving dedicated browser session over CDP.
- [x] **REQ-LINK-02:** Support ProseMirror contenteditable input injection via CDP `Input.insertText`.
- [x] **REQ-LINK-03:** Automate LinkedIn PDF document carousel upload and submission.
- [x] **REQ-LINK-04:** Read-back verification on LinkedIn recent activity timeline (`/recent-activity/all/`).
- [x] **REQ-LINK-05:** Enforce 4-hour minimum gap between LinkedIn posts.

### Phase 4: Meta Threads Official API Adapter & Content Repurposer
- [x] **REQ-THRD-01:** Implement `adapters/threads.py` using browser CDP automation without cloud hosting.
- [x] **REQ-THRD-02:** Zero cloud dependency image attachments via CDP DOM input files.
- [x] **REQ-REPURP-01:** Polymorphic content repurposing schema in `drafts/YYYY-MM-DD.json` (1 research item -> 4 channel drafts).

### Phase 5: Unified Ledger & Cross-Platform Engagement
- [x] **REQ-LEDGER-01:** Upgrade `state.json` to schema v2.0 with per-platform status dictionary.
- [x] **REQ-RETRY-01:** Independent platform retry on partial failure without double-posting to successful channels.
- [x] **REQ-FEEDBACK-01:** Metrics scraper and closed-loop feedback into `references/voice-profile.local.md`.

### Phase 6: Production Wisdom & Enforcement-First Hardening
- [x] **REQ-RISK-01:** Document honest platform automation risks, account danger, DOM breakage scenarios, and vision verification trust boundaries in README and docs.
- [x] **REQ-GUARD-01:** Implement enforcement-first guard rails in code (`validator.py` / `due.py` / `post.py`) preventing unmeasured limits, duplicate text, wrong handles, engagement bait, and fabricated claims.
- [x] **REQ-VOICE-01:** Implement voice authenticity measurement ritual in `voice_profile.py` with top post sampling, mandatory "do-not" lists, and hard stops when profiles are missing.
- [x] **REQ-GATE-01:** Implement lightweight `scripts/gate.py` with byte-identical `IDLE` stdout contract to enable $0-cost cron schedule monitoring.
- [x] **REQ-TEST-02:** Build comprehensive real-world validation test suite including E2E pipeline dry-run, carousel rendering verification, and polymorphic multi-platform adaptation tests.
- [x] **REQ-DOCS-01:** Consolidate documentation into an authoritative Step 0->1->2 onboarding journey and document "Pitfalls Already Paid For" (10 hard-won production lessons).
- [x] **REQ-DEP-01:** Formally document the minimal 3-dependency architecture philosophy and zero-cost adapter expansion model.
- [x] **REQ-WARM-01:** Document and enforce account safety warm-up protocols (profile completion, manual posts/replies, 1 post/day ramp).
- [x] **REQ-SRC-01:** Implement Hard Rule 3b ("Read Before You Write") verifying that post claims trace directly to scraped research sources.
- [x] **REQ-WIZARD-01:** Expand onboarding wizard ceremony with live character limit measurement (`post.py measure --save`) and mandatory supervised first-post verification.



