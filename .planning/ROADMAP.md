# Roadmap: OmniPost Multi-Platform Evolution

## Overview

OmniPost evolves from a proven single-platform X autonomous publishing engine into a multi-platform syndicate. Each phase incrementally introduces new channel adapters and capabilities while guaranteeing that existing channels remain 100% operational.

## Phases

- [x] **Phase 1: Adapter Foundation & Bluesky Integration** - Modularize `PlatformAdapter` abstraction, extract X adapter, and implement native ATProto Bluesky adapter with rich text facets.
- [x] **Phase 2: Zero-Dependency Visual Pipeline** - Programmatic Pillow infocards and HTML + CDP `Page.printToPDF` multi-slide PDF carousels.
- [x] **Phase 3: LinkedIn CDP Adapter** - Stealth browser automation for LinkedIn posts and multi-page PDF document carousels.
- [x] **Phase 4: Meta Threads CDP Adapter & Content Repurposer** - Browser CDP automation for Threads and polymorphic 1-insight-to-4-channel drafting.
- [x] **Phase 5: Unified Ledger & Cross-Platform Engagement** - Atomic multi-platform ledger in `state.json` v2.0, partial-failure isolation, and closed-loop feedback.
- [x] **Phase 6: Production Wisdom & Enforcement-First Hardening** - Port TweetyTweets production rigor: risk transparency, code guardrails, voice measurement ritual, $0-cost schedule gate, and E2E integration tests.
- [x] **Phase 8: Visual Taste Overhaul & CLI Draft Dispatcher** - Slot-aware CLI publishing, semantic insight slide generation, Geist font & single-accent visual overhaul, zero-empty-void panel guarantees.
- [x] **Phase 9: Live Drop Hardening, CDP Drag-and-Drop & Autonomous Dynamic Generation** - Mandatory failure telemetry, fast <5s LinkedIn drag-and-drop PDF upload, X button & error propagation fix, Threads Lexical synthetic event hydration, and dynamic daily draft loop.
- [x] **Phase 10: Dynamic Multi-Image Generation & Platform Character Calibration** - Dynamic 1-3 image cards based on content depth, elimination of title echoing, LinkedIn fast Media button upload, Threads modal trigger fix, and full platform character limit optimization (LinkedIn 3000, Threads 500, Bluesky 300, X 280).
- [ ] **Phase 11: Content Integrity & Relevance Gate** - Reject off-topic research, fail closed on missing summaries, and generate topic-specific bullets/takeaways instead of identical fallback boilerplate.
- [ ] **Phase 12: Truthful Publish State & Idempotency** - Record verified vs unverified separately, serialize state writes, cancel timed-out publishes, and prevent duplicate posts across retries and manual runs.
- [ ] **Phase 13: Platform Adapter Recovery & Permalinks** - Harden LinkedIn composer detection/rate limiting and return real Threads/X permalinks with complete media attachments.
- [ ] **Phase 14: Platform Copy Calibration & Media Contract** - Enforce real per-platform character limits and explicitly select image vs PDF carousel per platform.
- [ ] **Phase 15: 9:16 Storybook Renderer & Deterministic Assets** - Replace 1080x1080 generic cards with topic-driven 1080x1920 storybook cards using embedded fonts and hard asset failures.
- [ ] **Phase 16: Privacy, Error Taxonomy & CI Guardrails** - Redact failure artifacts, replace silent broad exceptions with typed errors, and add fixture-DOM/golden-image/live-smoke tests.
- [ ] **Phase 17: End-to-End Overhaul Verification & Live Drop** - Prove the overhaul with dry-run, controlled live publishing, verified URLs, duplicate checks, and a telemetry report.
- [x] **Phase 18: Ingestion & Text Quality Overhaul** - Sanitize raw feed metadata (arXiv/HN), eliminate LinkedIn/Threads copy duplication, enforce word-boundary safe limits without dangling conjunctions, and add humanity guardrails.
- [x] **Phase 19: Visual Taste-Design Architecture** - Establish semantic design contract (`render/DESIGN.md`), overhaul 9:16 storybook cards with architecture flow and code widgets, and re-architect 1080x1080 carousels for viral 4-slide narrative.
- [ ] **Phase 20: Growth & Pipeline Fixes (Post-Merge)** - Close what PR #15 did not: sanitize every ingestion path including historical swipe banks, encode the tension→entity→axiom post template, verify production runs merged `main`, and diagnose LinkedIn's 3.8% reach.

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

**Plans**: 2 plans (Completed)

Plans:

- [x] 03-01: LinkedIn CDP Session & ProseMirror Injection Driver
- [x] 03-02: Document Carousel Upload & Activity Timeline Verification

### Phase 4: Meta Threads CDP Adapter & Content Repurposer

**Goal**: Implement Meta Threads browser automation via CDP and build the polymorphic prompt matrix that converts 1 research insight into 4 distinct channel formats.
**Depends on**: Phase 3
**Requirements**: REQ-THRD-01, REQ-THRD-02, REQ-REPURP-01
**Success Criteria** (what must be TRUE):

  1. `adapters/threads.py` creates and publishes threads via browser CDP automation without cloud hosting.
  2. Content Repurposer generates platform-tailored drafts in `drafts/YYYY-MM-DD.json`.

**Plans**: 2 plans

Plans:

- [x] 04-01: Meta Threads CDP Adapter
- [x] 04-02: Polymorphic Content Repurposer Engine & Multi-Draft Dispatch

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

- [x] 05-01: Multi-Platform State Ledger & Partial-Failure Retry Engine
- [x] 05-02: Cross-Platform Metrics Aggregation & Feedback Loop

### Phase 6: Production Wisdom & Enforcement-First Hardening

**Goal**: Hardening OmniPost with battle-tested production wisdom from TweetyTweets: explicit risk honesty, code-level guardrails against bad posts, voice authenticity measurement rituals, $0-cost idle schedule gating, E2E multi-platform validation tests, and full onboarding ceremonies.
**Depends on**: Phase 5
**Requirements**: REQ-RISK-01, REQ-GUARD-01, REQ-VOICE-01, REQ-GATE-01, REQ-TEST-02, REQ-DOCS-01, REQ-DEP-01, REQ-WARM-01, REQ-SRC-01, REQ-WIZARD-01
**Success Criteria** (what must be TRUE):

  1. `README.md` and `USERGUIDE.md` explicitly detail account automation risks, anti-spam warm-up protocols, DOM fragility realities, and trust boundaries on vision models.
  2. `validator.py`, `due.py`, and `post.py` enforce hard guardrails: rejecting unmeasured character ceilings, duplicate text, unverified handles, engagement bait, and unverified factual claims.
  3. `scripts/voice_profile.py` implements a structured measurement ritual using top posts and enforces mandatory "do-not" style rules.
  4. `scripts/gate.py` provides a byte-identical `IDLE` stdout contract to eliminate idle LLM invocation costs in cron/systemd setups.
  5. An E2E test suite (`tests/test_integration_e2e.py`, `tests/test_carousel_rendering.py`, `tests/test_multiplatform_adaptation.py`) verifies full lifecycle behavior without flaky network dependencies.
  6. `setup.py` and `wizard.py` run a complete onboarding ceremony with character ceiling measurement and supervised first-post verification.

**Plans**: 3 plans

Plans:

- [x] 06-01: Hard Rules, Guardrails & Source Verification Engine
- [x] 06-02: Zero-Cost Idle Gate, Voice Measurement Ritual & Onboarding Ceremony
- [x] 06-03: Real-World E2E Test Suite, Risk Transparency & Authoritative Documentation

### Phase 7: Consumer Onboarding, Platform-Native Synthesis & Resilience Polish

**Goal**: Elevate OmniPost v2.5 to a commercial consumer-ready desktop application with 1-click bootstrap, dynamic multi-provider model selection with live validation, platform-native content archetypes (X hook, LinkedIn carousel, Threads conversation, Bluesky insight), in-page LinkedIn toast verification, and lean network resilience.
**Depends on**: Phase 6
**Requirements**: REQ-BOOTSTRAP-01, REQ-WIZARD-MODEL-01, REQ-WIZARD-TELEGRAM-01, REQ-SYNTH-NATIVE-01, REQ-SYNTH-ARCHETYPES-01, REQ-LINK-TOAST-01, REQ-NET-RESIL-01, REQ-NOTIFY-RICH-01
**Success Criteria** (what must be TRUE):

  1. `setup.bat` and `setup.sh` provide zero-friction 1-click environment setup and launch `wizard.py`.
  2. `scripts/wizard.py` allows selecting between Gemini, OpenAI, Anthropic, and OpenRouter with custom model input and zero-token pre-flight probe validation.
  3. `scripts/wizard.py` performs a live Telegram bot ping test, preventing `400: chat not found`.
  4. `scripts/generate.py` outputs a structured 4-platform JSON payload tailored to each network's audience without arbitrary text slicing.
  5. `adapters/linkedin.py` captures `urn:li:activity` live from the feed submission toast with zero secondary navigation.
  6. `scripts/publish_now.py` probes connectivity via Google 204, handles network timeouts with amber Telegram warnings, and never hangs indefinitely.

**Plans**: 3 plans

Plans:

- [x] 07-01: 1-Click Root Bootstrap & Onboarding Ceremony with Dynamic Multi-Provider Model Selection & Telegram Validation
- [x] 07-02: Platform-Native Content & Audience Engagement Engine
- [x] 07-03: In-Page LinkedIn Toast Verification, Lean Network Resilience & Rich Telegram Alerts

### Phase 8: Visual Taste Overhaul & CLI Draft Dispatcher

**Goal**: Resolve draft dispatch failures for multi-slot daily schedules, eliminate content echoing, ban cheap numbered meta-labels, upgrade typography and design to Awwwards-caliber `/taste-design` and `/gpt-taste` standards, and enforce zero-empty-void rendering.
**Depends on**: Phase 7
**Requirements**: REQ-DISPATCH-SLOT-01, REQ-SYNTH-BULLETS-01, REQ-DESIGN-FONT-01, REQ-DESIGN-PALETTE-01, REQ-DESIGN-VOIDS-01
**Success Criteria** (what must be TRUE):

  1. `publish_now.py --draft drafts/YYYY-MM-DD.json` automatically unwraps the daily slots array without schema crash.
  2. `--slot <HH:MM>` allows on-demand publishing of any specific time slot.
  3. `scripts/generate.py` guarantees 3 distinct bullet points per slide and strictly bans cheap meta-labels (`01. Overview`, `02. Technical Context`).
  4. `render/template.html` adopts Google Fonts `Geist` + `Geist Mono` and unifies around a singular precision accent color.
  5. `render/carousel.py` guarantees zero empty `.card-panel` voids and replaces `"Swipe ➔"` with sleek pagination indicators.
  6. Dry-run and live PDF compilation pass with 100% visual integrity.

**Plans**: 4 plans

Plans:

- [x] 08-01: CLI Draft Dispatcher Slot Unwrapping & Fallback Handling
- [x] 08-02: Content Synthesis Integrity & Anti-Echo Semantic Slide Generation
- [x] 08-03: Visual Design Taste Overhaul (/taste-design & /gpt-taste)
- [x] 08-04: End-to-End Pipeline & Live Publishing Verification

### Phase 9: Live Drop Hardening, CDP Drag-and-Drop & Autonomous Dynamic Generation

**Goal**: Overcome blind DOM guessing with mandatory failure telemetry, implement fast <5s LinkedIn CDP drag-and-drop PDF upload, fix X button click & error propagation, resolve Threads Lexical synthetic event hydration, and build the autonomous dynamic daily draft & unique carousel pipeline.
**Depends on**: Phase 8
**Requirements**: REQ-TELEMETRY-01, REQ-CLI-DIAGNOSTIC-01, REQ-X-CLICK-01, REQ-LINK-DRAGDROP-01, REQ-THRD-LEXICAL-01, REQ-DYNAMIC-DRAFT-01, REQ-UNIQUE-CAROUSEL-01
**Success Criteria** (what must be TRUE):

  1. `shots/{platform}_fail.png` and `shots/{platform}_fail.html` capture automatically on any adapter failure.
  2. `scripts/test_adapter.py` allows testing X, Bluesky, LinkedIn, or Threads in isolation in under 15 seconds.
  3. `scripts/post.py` detects all tweetButton variants and propagates exact click failures without returning `error: None`.
  4. LinkedIn attaches PDF carousels in < 5 seconds via native CDP drag-and-drop simulation.
  5. Threads hydrates Lexical contenteditable area with synthetic event coordinates and focuses reliably.
  6. `publish_now.py --fresh` pulls live research, compiles today's 4-slot draft, renders unique PDF, and publishes across all 4 platforms without duplicate content issues.

**Plans**: 5 plans

Plans:

- [x] 09-01: Universal Failure Telemetry & Isolated Single-Platform Diagnostic CLI
- [x] 09-02: X (Twitter) Post Button & Error Propagation Hardening
- [x] 09-03: LinkedIn Native CDP Drag-and-Drop Implementation (< 5 Seconds)
- [x] 09-04: Threads Lexical ContentEditable Hydration & SyntheticEvent Focus
- [x] 09-05: Autonomous Dynamic Generation Loop & Unique Multi-Topic Scheduling

### Phase 10: Dynamic Multi-Image Generation & Platform Character Calibration

**Goal**: Replace rigid 4-page PDF carousels with dynamic 1–3 retina PNG visual cards based on content depth, eradicate title/body/bullet echoing, fix LinkedIn fast image uploads via the native Media button, resolve Threads modal triggering, and write platform-native copy maximized to each channel's character ceiling (LinkedIn: 3,000, Threads: 500, Bluesky: 300, X: 280).
**Depends on**: Phase 9
**Requirements**: REQ-ANTI-ECHO-01, REQ-DYNAMIC-DENSITY-01, REQ-PNG-RENDER-01, REQ-GPT-TASTE-VIS-01, REQ-LINK-MEDIA-01, REQ-THRD-MODAL-01, REQ-CHAR-CALIBRATION-01
**Success Criteria** (what must be TRUE):

  1. `scripts/generate.py` never echoes headline in body or bullets and selects 1, 2, or 3 cards dynamically.
  2. `render/cards.py` compiles 1080x1080 retina PNG cards using `/gpt-taste` standards (Geist font, emerald accent, zero void panels).
  3. `adapters/linkedin.py` attaches 1–3 PNGs via the standard `Media` button in < 1.5s with 100% reliability.
  4. `adapters/threads.py` triggers the composer dialog reliably and attaches 1–3 images.
  5. `scripts/repurpose.py` writes platform-native copy maximized to each channel's character limit.
  6. `publish_now.py --fresh` publishes across all 4 platforms with text explanation followed by visual image attachments.

**Plans**: 5 plans

Plans:

- [x] 10-01: Content Engine Anti-Duplication & Dynamic Card Density
- [x] 10-02: CDP Retina Multi-Image PNG Renderer (1 to 3 Images)
- [x] 10-03: Multi-Platform Adapter Image Harmonization (LinkedIn & Threads Fix)
- [x] 10-04: Full Platform Character Optimization & Copy Crafting
- [x] 10-05: End-to-End Dynamic Multi-Image Pipeline Verification & Live Drop

### Phase 11: Content Integrity & Relevance Gate
**Goal**: Stop publishing off-topic Hacker News items and eliminate the identical fallback bullets, domain-as-takeaway text, and hardcoded LinkedIn boilerplate. Every draft must be topically relevant, grounded in a real source summary, and unique across the day's slots.
**Depends on**: Phase 10
**Requirements**: REQ-RELEVANCE-01, REQ-FAILCLOSED-01, REQ-TAKEAWAY-01, REQ-BOILERPLATE-01, REQ-UNIQUENESS-01
**Success Criteria** (what must be TRUE):
  1. A political/non-engineering HN item is rejected before generation and never reaches a draft.
  2. An item without a usable summary is requeued or skipped; the generic `"Analyzing architectural tradeoffs... for {title}"` sentence is never published.
  3. Two different topics produce different bullets and takeaways; no domain name or `"Verified Reference"` appears as a takeaway.
  4. LinkedIn copy contains no hardcoded "Architectural Bottleneck", "Production Principles", or "cards below" boilerplate.
  5. A day's slots cannot contain duplicate bullet sets or duplicate post text.
**Plans**: 1 plan

Plans:
- [ ] 11-01: Relevance Gate, Fail-Closed Synthesis & Topic-Derived Copy

### Phase 12: Truthful Publish State & Idempotency
**Goal**: Make `state.json` tell the truth about what was actually verified and make every publish path idempotent, so timeouts, retries, concurrent runs, and manual publishes cannot silently skip a missing post or create a duplicate.
**Depends on**: Phase 11
**Requirements**: REQ-STATE-VERIFIED-01, REQ-IDEMPOTENCY-01, REQ-STATE-LOCK-01, REQ-STATE-RECOVERY-01, REQ-TIMEOUT-CANCEL-01
**Success Criteria** (what must be TRUE):
  1. `record_platform_status` records `published_verified`, `submitted_unverified`, or `failed`; only `published_verified` satisfies `is_platform_done`.
  2. A timed-out publish is cancelled and reconciled against the platform before any retry is recorded.
  3. A single cross-process lock serializes state read-modify-write between autoposter and manual runs.
  4. A corrupt `state.json` is quarantined and restored from backup; it is never overwritten with an empty state.
  5. Manual `publish_now` refuses an already-published slot unless `--force` is passed.
**Plans**: 1 plan

Plans:
- [ ] 12-01: Verified-State Semantics, State Lock, Cancellable Timeout & Idempotency Keys

### Phase 13: Platform Adapter Recovery & Permalinks
**Goal**: Recover the live LinkedIn composer path, repair the dead LinkedIn rate-limit guardrail, return real post permalinks from Threads, and stop X from dropping cards 2–3.
**Depends on**: Phase 12
**Requirements**: REQ-LINK-COMPOSER-02, REQ-LINK-RATE-02, REQ-THRD-PERMALINK-01, REQ-X-MEDIA-01, REQ-ADAPTER-ERROR-01
**Success Criteria** (what must be TRUE):
  1. LinkedIn composer detection uses scoped selectors, waits for the dialog/editor, and never clicks the generic `artdeco-button--tertiary` fallback.
  2. LinkedIn rate limiting reads `platforms.linkedin.at`, parses timezone-aware timestamps, and fails closed.
  3. Threads returns the real post permalink when the toast/activity readback succeeds; otherwise it reports unverified instead of the profile URL.
  4. X attaches all rendered cards up to its `max_images` limit.
  5. Adapter failures raise typed errors with actionable context instead of generic timeouts.
**Plans**: 1 plan

Plans:
- [ ] 13-01: LinkedIn Composer/Rate-Limit Recovery, Threads Permalinks & X Multi-Card Attachment

### Phase 14: Platform Copy Calibration & Media Contract
**Goal**: Enforce each platform's real counting rules and limits, eliminate mid-word truncation and Threads overflow, and make image-vs-PDF carousel selection explicit instead of dead capability flags.
**Depends on**: Phase 13
**Requirements**: REQ-CHAR-LIMITS-02, REQ-TRUNCATION-01, REQ-CAROUSEL-CONTRACT-01, REQ-COPY-MIN-01
**Success Criteria** (what must be TRUE):
  1. One shared limit utility handles X weighted characters, Bluesky graphemes, Threads 500, and LinkedIn 3,000.
  2. Truncation happens on word boundaries with an ellipsis; no formatter cuts mid-word.
  3. X lands in 220–275, Bluesky in 240–295, Threads in 350–480 (never >500), and LinkedIn in 1,500–2,500 when the source supports it.
  4. Emoji and CJK samples pass every platform's real limit test.
  5. `media_type` is explicit per platform; LinkedIn either sends a real PDF carousel or the capability/doc claim is removed.
**Plans**: 1 plan

Plans:
- [ ] 14-01: Shared Limit Engine, Word-Boundary Truncation & Explicit Media Contract

### Phase 15: 9:16 Storybook Renderer & Deterministic Assets
**Goal**: Replace the fixed 1080x1080 generic card engine with a 1080x1920 topic-driven storybook renderer that embeds fonts, derives every slide from the topic, and fails loudly when an asset cannot be produced.
**Depends on**: Phase 14
**Requirements**: REQ-RENDER-916-01, REQ-STORY-SLIDES-01, REQ-FONT-DETERMINISM-01, REQ-ASSET-FAIL-01, REQ-CARD-TESTS-01
**Success Criteria** (what must be TRUE):
  1. Every card is 1080x1920 at 1x (2160x3840 at 2x) with header, hero, and footer bands.
  2. Slides 2–3 are derived from the topic; the hardcoded "Engineering Implementation & Tradeoffs", "Deterministic State Architecture", and "Production Reliability Checklist" headlines are gone.
  3. Fonts are embedded/local; rendering succeeds offline and waits for `document.fonts.ready` plus images, with no fixed 1.2s sleep.
  4. A card-render failure raises and blocks the draft; it never silently degrades to text-only.
  5. Golden tests assert dimensions, offline rendering, and different content for different topics.
**Plans**: 1 plan

Plans:
- [ ] 15-01: 9:16 Storybook Template, Topic-Driven Slides & Deterministic Rendering

### Phase 16: Privacy, Error Taxonomy & CI Guardrails
**Goal**: Prevent failure artifacts from leaking logged-in DOM, replace silent broad exception handling with typed errors, and add tests that catch selector drift, dimension regressions, and unsafe artifacts.
**Depends on**: Phase 15
**Requirements**: REQ-ARTIFACT-PRIVACY-01, REQ-ERROR-TAXONOMY-01, REQ-CI-CONTRACT-01
**Success Criteria** (what must be TRUE):
  1. Failure artifacts write under `ROOT/shots`, redact known PII/tokens, have bounded retention, and are never attached raw to notifications.
  2. Adapters use specific exception types and log actionable context; unexpected exceptions fail the platform.
  3. CI includes fixture-DOM selector contract tests, 9:16 golden-image tests, and a manual-gated live smoke job.
  4. The test suite no longer pins 1080x1080 as the only valid card size.
**Plans**: 1 plan

Plans:
- [ ] 16-01: Artifact Redaction, Typed Adapter Errors & CI Contract/Golden Tests

### Phase 17: End-to-End Overhaul Verification & Live Drop
**Goal**: Prove the full overhaul with a deterministic dry-run and one controlled live drop, including relevance, uniqueness, limits, 9:16 assets, verified URLs, duplicate checks, and a telemetry report.
**Depends on**: Phase 16
**Requirements**: REQ-E2E-OVERHAUL-01, REQ-LIVE-VERIFY-01
**Success Criteria** (what must be TRUE):
  1. `python scripts/publish_now.py --fresh --dry-run` generates relevant, unique copy and 9:16 cards for every slot.
  2. Two different source topics produce different bullets, takeaways, and card content.
  3. A controlled live drop publishes to all enabled platforms and records verified URLs where readback succeeds.
  4. A forced timeout and a repeated manual run produce no duplicate post.
  5. `docs/OVERHAUL_VERIFICATION.md` reports per-platform status, verification, URL, content hash, asset dimensions, and limit counts.
**Plans**: 1 plan

Plans:
- [ ] 17-01: Overhaul Dry-Run, Controlled Live Drop & Telemetry Report

### Phase 18: Ingestion & Text Quality Overhaul
**Goal**: Eliminate raw scraper metadata leakage, cross-section copy duplication, and mid-word truncation across all 4 publishing channels (X, Bluesky, LinkedIn, Threads).
**Depends on**: Phase 17
**Requirements**: REQ-SAN-01, REQ-DEDUPE-01, REQ-BOUND-01, REQ-GUARD-09
**Success Criteria** (what must be TRUE):
  1. Feeds with arXiv announcements, HN links, or CMS signatures are sanitized at collection before landing in swipe bank.
  2. LinkedIn copy never mirrors the thesis between body, bullet 1, and bottom line (token similarity < 60%).
  3. LinkedIn boilerplate headers ('What changes in practice:', 'Bottom line:') are replaced with dynamic connectors.
  4. Threads copy removes redundant bullets and eliminates the forced question CTA.
  5. Truncation across all platforms preserves word boundaries and never ends with dangling conjunctions ('and...', 'with...').
  6. The draft guardrail rejects any post containing raw scraper metadata or broken word endings.
**Plans**: 1 plan

Plans:
- [x] 18-01: Feed Ingestion Sanitization, Copy Deduplication, Safe Limits & Guardrail Gate

### Phase 19: Visual Taste-Design Architecture
**Goal**: Upgrade OmniPost's visual assets (9:16 PNG storybook cards and 1080x1080 PDF carousels) from generic AI templates to high-agency, viral /taste-design standards.
**Depends on**: Phase 18
**Requirements**: REQ-DESIGN-CONTRACT-01, REQ-STORYBOOK-ARCH-01, REQ-CAROUSEL-VIRAL-01
**Success Criteria** (what must be TRUE):
  1. 
`render/DESIGN.md` formally defines semantic design tokens, typography rules, widget layouts, and anti-patterns.
  2. 9:16 Storybook cards use a deep Zinc slate base (#090D16) with 1px whisper borders and zero multi-color radial glow gradients.
  3. The pulsing green neon glowing circle (.brand-dot) is removed in favor of crisp monospace badges.
  4. Cards support modular Architecture Flow Panels and Terminal Code Panels instead of raw abstract paragraph dumps.
  5. 1080x1080 carousels render 100% offline with vendored base64 Geist fonts (no Google Fonts network requests).
  6. Carousels enforce a 4-slide viral engineering narrative (Hook -> Problem Anatomy -> Architecture -> Actionable Checklist).
**Plans**: 1 plan

Plans:
- [x] 19-01: Semantic Design Contract, High-Agency Storybook Cards & Viral Offline Carousels

### Phase 20: Growth & Pipeline Fixes (Post-Merge)

**Goal**: Finish `GROWTH_AND_PIPELINE_FIX_PLAN.md` after PR #15 closed the publishing defects: close the ingestion hygiene gap, encode the post template that already worked, prove production runs merged `main`, and diagnose why LinkedIn reaches 3.8% of 690 followers.
**Depends on**: Phase 19
**Requirements**: REQ-INGEST-SWIPE-01, REQ-CONTENT-TENSION-01, REQ-DEPLOY-MAIN-01, REQ-LINKEDIN-REACH-01, REQ-PROFILE-COPY-01
**Success Criteria** (what must be TRUE):

  1. No item reaches generation unsanitized; historical `swipe/*.json` files written before `8fd5da7` contain no arXiv/Article URL/Announce Type markers after the audit.
  2. `build_system_prompt` states the tension → real entity → engineering axiom template and still forbids engagement-bait closers.
  3. The deployed runner exposes the merged `check_measured` and per-platform guardrail code, and a read-only container `due.py show` run succeeds without publishing.
  4. LinkedIn reach diagnosis names which of the four hypotheses in §2.5 holds, with evidence; no new LinkedIn post is scheduled until it is answered.
  5. Profile copy (§4) and the 10-comments/day protocol (§6) are executed manually and recorded.

**Already complete (PR #15, merged as `765a5de`)**: Defects 1, 2, 4, 5, 6 — see the `already_done` frontmatter in `20-01-PLAN.md` and the mapping in `20-CONTEXT.md`. Defect 3 remains a hygiene audit, not a confirmed live leak.
**Plans**: 2 plans

Plans:
- [ ] 20-01: Ingestion Boundary Sanitization & Tension-Template Prompt Encoding
- [ ] 20-02: Deployed-`main` Verification, LinkedIn Reach Diagnosis & Manual Profile/Channel Checklist
