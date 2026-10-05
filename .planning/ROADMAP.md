# Roadmap: OmniPost Multi-Platform Evolution

## Overview

OmniPost evolves from a proven single-platform X autonomous publishing engine into a multi-platform syndicate. Each phase incrementally introduces new channel adapters and capabilities while guaranteeing that existing channels remain 100% operational.

## Phases

- [x] **Phase 1: Adapter Foundation & Bluesky Integration** - Modularize `PlatformAdapter` abstraction, extract X adapter, and implement native ATProto Bluesky adapter with rich text facets.
- [x] **Phase 2: Zero-Dependency Visual Pipeline** - Programmatic Pillow infocards and HTML + CDP `Page.printToPDF` multi-slide PDF carousels.
- [ ] **Phase 3: LinkedIn CDP Adapter** - Stealth browser automation for LinkedIn posts and multi-page PDF document carousels.
- [ ] **Phase 4: Meta Threads API & Content Repurposer** - Official Graph API publishing and polymorphic 1-insight-to-4-channel drafting.
- [ ] **Phase 5: Unified Ledger & Cross-Platform Engagement** - Atomic multi-platform ledger in `state.json` v2.0, partial-failure isolation, and closed-loop feedback.

## Phase Details

### Phase 1: Adapter Foundation & Bluesky Integration
**Goal**: Decouple publishing into a standard `PlatformAdapter` interface, preserve working X functionality in `adapters/x.py`, implement zero-browser Bluesky publishing over ATProto XRPC, and enable multi-platform configuration toggles.
**Depends on**: Nothing (builds on stable V1.0.1 baseline)
**Requirements**: REQ-ADAPT-01, REQ-ADAPT-02, REQ-X-01, REQ-BSKY-01, REQ-BSKY-02, REQ-CFG-01, REQ-TEST-01
**Success Criteria** (what must be TRUE):
  1. `adapters/base.py` exports `PlatformAdapter`, `PlatformCapabilities`, `PublishPayload`, and `PublishResult`.
  2. `adapters/x.py` implements `PlatformAdapter` cleanly and passes existing dry-run compose and profile verification tests.
  3. `adapters/bluesky.py` successfully creates sessions, formats UTF-8 byte facets for links/mentions, and publishes text records to ATProto.
  4. `config.json` allows enabling/disabling platforms independently via `platforms.x` and `platforms.bluesky`.
  5. Full unit test suite passes with zero regressions on existing X functionality.
**Plans**: 3 plans (Completed)

Plans:
- [x] 01-01: Abstract Adapter Interface & X Adapter Extraction
- [x] 01-02: Bluesky ATProto XRPC Adapter with Rich Text Byte Facets
- [x] 01-03: Multi-Platform Configuration & Orchestrator CLI Integration

### Phase 2: Zero-Dependency Visual Pipeline
**Goal**: Build automated graphic generation for dark-mode 16:9 infocards (Pillow) and 1080x1080 vector PDF carousels (HTML + CDP `Page.printToPDF`) without heavy C-library dependencies.
**Depends on**: Phase 1
**Requirements**: REQ-VIS-01, REQ-VIS-02, REQ-VIS-03
**Success Criteria** (what must be TRUE):
  1. `render/infocard.py` generates 16:9 dark-mode PNG cards from structured text.
  2. `render/carousel.py` generates clean multi-slide vector PDF carousels using CDP `Page.printToPDF`.
  3. Media payloads cleanly attach to X and Bluesky posts.
**Plans**: 2 plans (Completed)

Plans:
- [x] 02-01: Programmatic Infocard Renderer with Pillow
- [x] 02-02: CDP HTML-to-PDF Carousel Builder & Media Attachment Flow

### Phase 3: LinkedIn CDP Adapter
**Goal**: Build a dedicated LinkedIn browser automation adapter that supports long-form text, multi-page PDF carousel uploads, and profile activity read-back verification.
**Depends on**: Phase 2
**Requirements**: REQ-LINK-01, REQ-LINK-02, REQ-LINK-03, REQ-LINK-04, REQ-LINK-05
**Success Criteria** (what must be TRUE):
  1. `adapters/linkedin.py` successfully injects text into LinkedIn's ProseMirror editor via CDP.
  2. PDF carousels created in Phase 2 upload seamlessly to LinkedIn document shares.
  3. Verification reads back published posts from the LinkedIn activity feed.
**Plans**: 2 plans

Plans:
- [ ] 03-01: LinkedIn CDP Session & ProseMirror Injection Driver
- [ ] 03-02: Document Carousel Upload & Activity Timeline Verification

### Phase 4: Meta Threads API & Content Repurposer
**Goal**: Implement Meta Threads official Graph API integration and build the polymorphic prompt matrix that converts 1 research insight into 4 distinct channel formats.
**Depends on**: Phase 3
**Requirements**: REQ-THRD-01, REQ-THRD-02, REQ-REPURP-01
**Success Criteria** (what must be TRUE):
  1. `adapters/threads.py` creates and publishes containers via Meta Graph API.
  2. Content Repurposer generates platform-tailored drafts in `drafts/YYYY-MM-DD.json`.
**Plans**: 2 plans

Plans:
- [ ] 04-01: Threads Official API Container Adapter
- [ ] 04-02: Multi-Channel Content Repurposer Prompt Matrix

### Phase 5: Unified Ledger & Cross-Platform Engagement
**Goal**: Implement atomic per-platform tracking in `state.json` v2.0, support isolated retries on partial publishing failures, and close the loop with analytics.
**Depends on**: Phase 4
**Requirements**: REQ-LEDGER-01, REQ-RETRY-01, REQ-FEEDBACK-01
**Success Criteria** (what must be TRUE):
  1. `state.json` tracks per-platform status atomically.
  2. Partial failures allow retrying failed channels without double-posting to successful ones.
  3. Engagement metrics feed back into voice profiling.
**Plans**: 2 plans

Plans:
- [ ] 05-01: Multi-Platform State Ledger & Partial-Failure Retry Engine
- [ ] 05-02: Cross-Platform Metrics Aggregation & Feedback Loop
