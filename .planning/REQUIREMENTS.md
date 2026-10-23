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

### Phase 11: Content Integrity & Relevance Gate
- [ ] **REQ-RELEVANCE-01:** Score every research item against an AI/engineering taxonomy, blocklist, and voice profile; reject items below threshold before generation.
- [ ] **REQ-FAILCLOSED-01:** Requeue or skip items without a usable source summary; never synthesize the generic `"Analyzing architectural tradeoffs..."` placeholder.
- [ ] **REQ-TAKEAWAY-01:** Derive takeaways from topic content; never use a source domain, `"Verified Reference"`, or an unrelated hardcoded sentence.
- [ ] **REQ-BOILERPLATE-01:** Remove hardcoded LinkedIn paragraphs and ungrammatical `"Why {headline} Matters in Production"` titles; derive every section from the topic.
- [ ] **REQ-UNIQUENESS-01:** Enforce cross-slot uniqueness for bullets, takeaways, and post text within a day.

### Phase 12: Truthful Publish State & Idempotency
- [ ] **REQ-STATE-VERIFIED-01:** Record `published_verified`, `submitted_unverified`, or `failed`; only `published_verified` counts as done.
- [ ] **REQ-IDEMPOTENCY-01:** Key every dispatch by `(date, slot, platform)` and reconcile before retrying a timeout.
- [ ] **REQ-STATE-LOCK-01:** Serialize `state.json` read-modify-write across processes with a bounded lock.
- [ ] **REQ-STATE-RECOVERY-01:** Quarantine corrupt state, restore from backup, and never overwrite it with an empty state.
- [ ] **REQ-TIMEOUT-CANCEL-01:** Cancel a timed-out publish instead of waiting for the worker; never record failed until reconciliation completes.

### Phase 13: Platform Adapter Recovery & Permalinks
- [ ] **REQ-LINK-COMPOSER-02:** Detect the LinkedIn composer with scoped selectors and wait for the dialog/editor; remove the generic tertiary-button fallback.
- [ ] **REQ-LINK-RATE-02:** Read `platforms.linkedin.at`, use timezone-aware parsing, and fail closed on rate-limit errors.
- [ ] **REQ-THRD-PERMALINK-01:** Return the real Threads post permalink or report unverified; never return the profile URL as the post URL.
- [ ] **REQ-X-MEDIA-01:** Attach all rendered cards up to each platform's `max_images`, including X.
- [ ] **REQ-ADAPTER-ERROR-01:** Raise typed adapter errors with actionable context instead of broad silent catches.

### Phase 14: Platform Copy Calibration & Media Contract
- [ ] **REQ-CHAR-LIMITS-02:** Implement one limit utility for X weighted characters, Bluesky graphemes, Threads 500, and LinkedIn 3,000.
- [ ] **REQ-TRUNCATION-01:** Truncate on word boundaries with an ellipsis; never cut mid-word.
- [ ] **REQ-COPY-MIN-01:** Enforce platform minimums (X 220, Bluesky 240, Threads 350, LinkedIn 1,500 when source depth supports it).
- [ ] **REQ-CAROUSEL-CONTRACT-01:** Choose image vs PDF carousel explicitly per platform and wire or remove the PDF capability.

### Phase 15: 9:16 Storybook Renderer & Deterministic Assets
- [ ] **REQ-RENDER-916-01:** Render 1080x1920 cards (2160x3840 at 2x) with header, hero, and footer bands.
- [ ] **REQ-STORY-SLIDES-01:** Derive every slide's headline, body, and bullets from the topic; remove hardcoded slides 2–3.
- [ ] **REQ-FONT-DETERMINISM-01:** Embed or vendor fonts, wait for fonts/images, and render offline without fixed sleeps.
- [ ] **REQ-ASSET-FAIL-01:** Fail the draft when a required card asset cannot be rendered; never silently publish text-only.
- [ ] **REQ-CARD-TESTS-01:** Add dimension, offline, and topic-differentiation golden tests.

### Phase 16: Privacy, Error Taxonomy & CI Guardrails
- [ ] **REQ-ARTIFACT-PRIVACY-01:** Write artifacts under `ROOT/shots`, redact PII/tokens, cap retention, and never attach raw DOM to notifications.
- [ ] **REQ-ERROR-TAXONOMY-01:** Replace broad silent exceptions with typed errors and contextual logging.
- [ ] **REQ-CI-CONTRACT-01:** Add fixture-DOM selector tests, 9:16 golden tests, and a manual-gated live smoke job.

### Phase 17: End-to-End Overhaul Verification & Live Drop
- [ ] **REQ-E2E-OVERHAUL-01:** Prove relevance, uniqueness, limits, 9:16 assets, and duplicate safety in a deterministic dry-run.
- [ ] **REQ-LIVE-VERIFY-01:** Run one controlled live drop, record verified URLs where available, and publish a telemetry report.



