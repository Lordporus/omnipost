# Requirements: OmniPost V2 Multi-Platform Expansion

## Functional Requirements

### Phase 1: Adapter Foundation & Bluesky Integration
- [ ] **REQ-ADAPT-01:** Abstract base class `PlatformAdapter` with standard contracts (`check_session`, `publish`, `verify`, `capabilities`).
- [ ] **REQ-ADAPT-02:** Dataclass contracts (`PlatformCapabilities`, `PublishPayload`, `PublishResult`) defined with typing.
- [ ] **REQ-X-01:** Extract monolithic `post.py` publishing logic into clean `adapters/x.py` implementing `PlatformAdapter`.
- [ ] **REQ-BSKY-01:** Implement `adapters/bluesky.py` using AT Protocol XRPC REST calls (`com.atproto.server.createSession`, `com.atproto.repo.uploadBlob`, `com.atproto.repo.createRecord`).
- [ ] **REQ-BSKY-02:** Parse and calculate UTF-8 byte slice indices for `app.bsky.richtext.facet` on URLs and @mentions.
- [ ] **REQ-CFG-01:** Update `config.json` schema to support per-platform toggle blocks (`platforms.x`, `platforms.bluesky`).
- [ ] **REQ-TEST-01:** Unit tests for adapter contracts, Bluesky facet calculations, and mock XRPC payloads.

### Phase 2: Zero-Dependency Visual Pipeline
- [ ] **REQ-VIS-01:** Implement `render/infocard.py` producing dark-mode 16:9 PNG cards (1200x675) with Pillow.
- [ ] **REQ-VIS-02:** Implement `render/carousel.py` producing 1080x1080 multi-page PDF carousels via HTML + CDP `Page.printToPDF`.
- [ ] **REQ-VIS-03:** Support media attachments in `PublishPayload` for both X and Bluesky.

### Phase 3: LinkedIn CDP Adapter
- [ ] **REQ-LINK-01:** Implement `adapters/linkedin.py` driving dedicated browser session over CDP.
- [ ] **REQ-LINK-02:** Support ProseMirror contenteditable input injection via CDP `Input.insertText`.
- [ ] **REQ-LINK-03:** Automate LinkedIn PDF document carousel upload and submission.
- [ ] **REQ-LINK-04:** Read-back verification on LinkedIn recent activity timeline (`/recent-activity/all/`).
- [ ] **REQ-LINK-05:** Enforce 4-hour minimum gap between LinkedIn posts.

### Phase 4: Meta Threads Official API Adapter & Content Repurposer
- [ ] **REQ-THRD-01:** Implement `adapters/threads.py` using Meta Graph API container creation and publishing.
- [ ] **REQ-THRD-02:** Token management and auto-refresh routines for 60-day long-lived tokens.
- [ ] **REQ-REPURP-01:** Polymorphic content repurposing schema in `drafts/YYYY-MM-DD.json` (1 research item -> 4 channel drafts).

### Phase 5: Unified Ledger & Cross-Platform Engagement
- [ ] **REQ-LEDGER-01:** Upgrade `state.json` to schema v2.0 with per-platform status dictionary.
- [ ] **REQ-RETRY-01:** Independent platform retry on partial failure without double-posting to successful channels.
- [ ] **REQ-FEEDBACK-01:** Metrics scraper and closed-loop feedback into `references/voice-profile.local.md`.
