# OmniPost: Multi-Platform Autonomous Publishing Pipeline
## Architectural Expansion Blueprint & Future Specification (V2.0)

---

## 1. Executive Summary & Core Philosophy

OmniPost V1 proved that high-leverage content publishing does not require predatory API subscriptions ($215+/month for X's basic tier) or brittle paid scrapers. It operates on an anti-fragile, zero-bloat foundation:

1. **Zero-Cost Open Intelligence:** Aggregates news from public endpoints (Hacker News Algolia API, RSS/Atom feeds, Reddit rendered DOM, and X search).
2. **Direct Browser Driving via CDP:** Controls real browser sessions via Chrome DevTools Protocol over WebSockets with standard Python (`websockets>=12.0`) without heavy frameworks (no Selenium, Playwright, or Puppeteer).
3. **Closed-Loop Verification:** Refuses to trust UI toasts; polls public profile DOM feeds and captures viewport screenshots as cryptographic/visual ground truth.
4. **Deterministic Cron Gate:** Evaluates schedule state using lightweight Python scripts; emits byte-identical `IDLE` strings during downtime to guarantee zero LLM token costs when idle.
5. **Grounded Voice Calibration:** Measures real post distributions (beats, hooks, devices, length) and enforces verified source attribution.

### The Objective of OmniPost V2
Evolve the single-platform X engine into a **unified, multi-platform syndicate**. A single verified research insight is autonomously repurposed, formatted, scheduled, published, and verified across **X, Bluesky, LinkedIn, and Threads**, with partial-failure isolation and zero platform cross-contamination.

---

## 2. OmniPost V1 Baseline vs. V2 Architecture

```
══════════════════════════════════════════════════════════════════════════
OMNIPOST V1 (CURRENT OPERATIONAL BASELINE)
══════════════════════════════════════════════════════════════════════════
[Research Engine] ──> [Voice Profiler] ──> [Jitter Gate] ──> [post.py] ──> [Real Browser] ──> [X.com]
 (HN/RSS/Reddit)      (Single Voice)        (due.py)        (Monolithic)     (CDP 9222/9444)    (Verified)

══════════════════════════════════════════════════════════════════════════
OMNIPOST V2 (MULTI-PLATFORM TARGET ARCHITECTURE)
══════════════════════════════════════════════════════════════════════════
                       ┌───────────────────────┐
                       │    RESEARCH ENGINE    │
                       │ (HN, RSS, Reddit, X)  │
                       └───────────┬───────────┘
                                   │ Raw Candidate Insights (~150/day)
                                   ▼
                       ┌───────────────────────┐
                       │  CONTENT REPURPOSER   │
                       │ (1 Insight -> 4 Nets) │
                       └───────────┬───────────┘
                                   │ Multi-Target Formatted Drafts
            ┌──────────────────────┼──────────────────────┬──────────────────────┐
            ▼                      ▼                      ▼                      ▼
      [X Formatter]        [Bluesky Formatter]   [LinkedIn Formatter]   [Threads Formatter]
       280c + Hook          300c + Byte Facets    1,500c + Carousel      500c Conversational
            │                      │                      │                      │
            ▼                      ▼                      ▼                      ▼
      ┌───────────┐          ┌───────────┐          ┌───────────┐          ┌───────────┐
      │ X Adapter │          │  Bluesky  │          │ LinkedIn  │          │  Threads  │
      │   (CDP)   │          │ (ATProto) │          │   (CDP)   │          │  (Graph)  │
      └─────┬─────┘          └─────┬─────┘          └─────┬─────┘          └─────┬─────┘
            │                      │                      │                      │
            └──────────────────────┼──────────────────────┴──────────────────────┘
                                   │ Per-Platform Publish & Verification Outcomes
                                   ▼
                       ┌───────────────────────┐
                       │    UNIFIED LEDGER     │
                       │  (state.json v2.0)    │
                       └───────────────────────┘
```

---

## 3. Platform Expansion Feasibility & Technical Audit

| Platform | Channel Type | Access Method | Cost | Anti-Bot Risk | Format Specialization | Verification Method |
|---|---|---|---|---|---|---|
| **X (Twitter)** | Microblog | Browser CDP (9222/9444) | $0 | Medium (mitigated by real profile + jitter) | Punchy 280c hook, 16:9 visual infocards | Read back profile timeline DOM + viewport screenshot |
| **Bluesky** | Decentralized Microblog | Native AT Protocol (XRPC HTTP) | $0 | Near Zero | 300c, rich facet spans, image blobs | Public XRPC API query (`getAuthorFeed` / `getRecord`) |
| **LinkedIn** | Professional Network | Browser CDP (Stealth) | $0 | High (aggressive behavioral fingerprinting) | Deep-dive essays (1,000–3,000c), **PDF Carousels** | Read back profile activity DOM (`/recent-activity/all/`) |
| **Threads (Meta)** | Conversational Network | Official Threads API (Graph REST) | $0 | Zero (official developer endpoint) | 500c conversational, image/carousel attachments | Graph API query (`GET /{threads-media-id}`) |
| **Reddit** | Community Forums | Free OAuth Script API / CDP | $0 | High (subreddit spam heuristics) | Discussion-first title + markdown body (zero link spam) | Query user submitted posts via public JSON |

---

## 4. Deep-Dive Platform Mechanics & Technical Corrections

### 1. Bluesky (AT Protocol / XRPC)
* **Authentication:** Generates a dedicated **App Password** (`Settings -> Privacy & Security -> App Passwords`). Never stores or exposes the master password.
* **Protocol Details:** Zero browser overhead. Communicates via clean HTTP JSON endpoints:
  1. `POST https://bsky.social/xrpc/com.atproto.server.createSession` (exchanges handle + app password for `accessJwt` and `did`).
  2. `POST https://bsky.social/xrpc/com.atproto.repo.uploadBlob` (uploads PNG/JPEG images up to 1MB, returning a blob reference CID).
  3. `POST https://bsky.social/xrpc/com.atproto.repo.createRecord` (commits the post record to repository `app.bsky.feed.post`).
* **Crucial Architectural Requirement (Rich Text Facets):**
  Unlike Twitter, Bluesky does **not** auto-link URLs or mentions. Mentions and links must be parsed into UTF-8 byte slices (`byteStart`, `byteEnd`) and attached as `facets` with `app.bsky.richtext.facet` schemas. Omitting facets results in plain, unclickable text.
* **Character Ceiling:** 300 Unicode graphemes.

### 2. LinkedIn (CDP Stealth Automation)
* **Why Not Official API?** LinkedIn's Community Management API requires verified enterprise developer status and complex OAuth refresh flows. CDP over dedicated profiles remains free and accessible.
* **Composer Architecture:**
  - Share modal: Triggered via `button[id*="share-box"]` or `button[data-view-name*="share-box"]`.
  - Text input: Uses a Quill/ProseMirror editor (`div.ql-editor[contenteditable="true"]`).
  - Input injection: Must use CDP `Input.insertText` with randomized typing delays (30–90ms) to ensure React/ProseMirror reconcilers register text.
* **Anti-Detection Safeguards:**
  - Inject CDP `Page.addScriptToEvaluateOnNewDocument` to mask `navigator.webdriver`.
  - Maintain a strict minimum 4-hour gap between posts.
* **Visual Weapon: PDF Carousels:**
  LinkedIn gives multi-page document carousels maximum algorithmic reach.
  * *Implementation Correction:* **Do NOT use `weasyprint`** on Windows/cross-platform environments due to heavy native GTK3/Pango/Cairo C-library dependencies.
  * *Recommended OmniPost Pattern:* Use **CDP Headless Chrome Print (`Page.printToPDF`)**! Since OmniPost already maintains a CDP connection to Chrome/Edge, it renders an HTML template with CSS print page-breaks (`break-after: page`) and invokes `Page.printToPDF` with zero external dependencies.

### 3. Threads by Meta (Official Threads Graph API)
* **Mechanism:** Meta's free official Threads API provides up to 250 published posts/day per user.
* **Authentication:** Requires a Meta Developer App with `threads_basic` and `threads_content_publish` scopes, exchanging for a long-lived user access token (valid 60 days, auto-refreshed).
* **Two-Step Publishing Pipeline:**
  1. `POST https://graph.threads.net/v1.0/{threads-user-id}/threads` (creates container with `media_type=TEXT` or `IMAGE`).
  2. `POST https://graph.threads.net/v1.0/{threads-user-id}/threads_publish` (publishes container with `creation_id`).
* **Crucial Architectural Requirement (Image Hosting):**
  Threads API requires images to be served from a **public HTTPS URL**. Local file paths cannot be uploaded directly via multipart form data.
  * *Solution:* For text-only posts, use direct API. For posts with images, provide an optional lightweight S3/R2/Cloudflare image uploader, or fall back to CDP browser upload.

### 4. Reddit (Selective Community Outreach)
* **Role:** Reddit is NOT a broadcast firehose. It is used exclusively for high-effort technical posts (1–2 times per week) on designated developer subreddits (e.g., `r/LocalLLaMA`, `r/SideProject`).
* **Mechanism:** Free personal script bot OAuth (`https://www.reddit.com/api/v1/access_token` with `grant_type=password` or refresh token), using standard library `urllib` or lightweight REST.

---

## 5. Architectural Contracts & Interfaces

To preserve system stability and modularity, OmniPost V2 enforces strict object schemas.

### 5.1 The `PlatformAdapter` Abstract Contract

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class PlatformCapabilities:
    max_characters: int
    supports_markdown: bool = False
    supports_images: bool = True
    max_images: int = 1
    supports_pdf_carousel: bool = False
    requires_public_image_url: bool = False

@dataclass
class PublishPayload:
    text: str
    media_paths: list[Path] = field(default_factory=list)
    media_type: str = "image"  # "image" | "carousel"
    extra_metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PublishResult:
    platform: str
    success: bool
    post_id: str | None = None
    url: str | None = None
    verified: bool = False
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """e.g. 'x', 'bluesky', 'linkedin', 'threads'"""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        ...

    @abstractmethod
    def check_session(self) -> dict[str, Any]:
        """Check credentials/session readiness without posting."""
        ...

    @abstractmethod
    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish post content and media."""
        ...

    @abstractmethod
    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Validate that the post is live on the public feed."""
        ...
```

### 5.2 Content Repurposer Output Schema (Multi-Format Draft)

A single research topic generates a polymorphic draft structure saved in `drafts/YYYY-MM-DD.json`:

```json
{
  "date": "2026-10-15",
  "topic_id": "open-llm-breakthrough",
  "source_url": "https://github.com/example/repo",
  "slots": [
    {
      "slot": "16:00",
      "kind": "ai_update",
      "due_at": "2026-10-15T16:15:00+05:30",
      "platforms": {
        "x": {
          "enabled": true,
          "text": "Daily AI updates | Day 42\n\nVector search is no longer the bottleneck in agentic workflows...\n\nFull architecture breakdown below.",
          "media": ["scratch/infocards/card_1600.png"],
          "media_type": "image"
        },
        "bluesky": {
          "enabled": true,
          "text": "Vector search is no longer the bottleneck in agentic workflows.\n\nThe real edge is deterministic state machines + tool calling with strict schemas. LLMs decide intent, code enforces execution.",
          "media": ["scratch/infocards/card_1600.png"],
          "media_type": "image"
        },
        "linkedin": {
          "enabled": true,
          "text": "Most engineering teams are scaling the wrong layer of their AI stack.\n\nHere is what we learned deploying 4 specialized autonomous agents...\n\n[Read the 5-slide architecture carousel below]",
          "media": ["scratch/carousels/agent_architecture.pdf"],
          "media_type": "carousel"
        },
        "threads": {
          "enabled": false,
          "text": "Quick question for AI engineers: are you still spending hours tuning vector chunks, or have you moved to deterministic state machines?"
        }
      }
    }
  ]
}
```

### 5.3 Unified Verification Ledger Schema (`state.json` v2.0)

`state.json` tracks execution across all channels atomically:

```json
{
  "version": "2.0.0",
  "last_ai_update": "2026-10-15T16:16:12Z",
  "posts": [
    {
      "id": "post-20261015-1600",
      "date": "2026-10-15",
      "slot": "16:00",
      "kind": "ai_update",
      "outcomes": {
        "x": {
          "success": true,
          "verified": true,
          "url": "https://x.com/your_handle/status/123456789",
          "published_at": "2026-10-15T16:16:00Z"
        },
        "bluesky": {
          "success": true,
          "verified": true,
          "url": "https://bsky.app/profile/your_handle.bsky.social/post/3kxxxx",
          "published_at": "2026-10-15T16:16:05Z"
        },
        "linkedin": {
          "success": true,
          "verified": true,
          "url": "https://linkedin.com/feed/update/urn:li:activity:987654321",
          "published_at": "2026-10-15T16:17:10Z"
        }
      }
    }
  ]
}
```

---

## 6. Zero-Dependency Visual Pipeline (Infocards & PDF Carousels)

Visual posts generate 3–5x greater organic reach across X, LinkedIn, and Threads.

### 6.1 Programmatic Infocards (`render/infocard.py`)
* Uses Python's standard `Pillow` (PIL) library.
* Canvas: Standard 16:9 dark-mode (1200x675px or 1920x1080px).
* Visual Rules:
  - Background: Deep slate (`#0B0F19`) with subtle radial gradient.
  - Typography: Clean sans-serif system fonts with hierarchical sizing.
  - Components: Source pill (e.g. `Hacker News Top #1`), headline, 3 key metric bullets, author handle footer.

### 6.2 Zero-Dependency PDF Carousel Generator (`render/carousel.py`)
* **Problem:** Competing tools require `weasyprint` or `playwright`, which drag massive dependencies and fail on standard Windows/Linux environments.
* **OmniPost Solution:**
  1. Generate a lightweight HTML string styling square cards (1080x1080px) with CSS:
     ```css
     @page { size: 1080px 1080px; margin: 0; }
     .slide { width: 1080px; height: 1080px; page-break-after: always; display: flex; ... }
     ```
  2. Open the temporary HTML file via OmniPost's existing CDP browser session.
  3. Call CDP `Page.printToPDF` with `{ "paperWidth": 11.25, "paperHeight": 11.25, "printBackground": true }`.
  4. Write resulting bytes directly to `scratch/carousels/{name}.pdf`.
  5. Result: 100% native vector PDF carousel ready for LinkedIn upload with **zero extra C-libraries**.

---

## 7. Phased Implementation Roadmap

To avoid breaking the working X pipeline, V2 is implemented in five strict, test-driven phases:

```
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Adapter Foundation & Bluesky Integration (Fastest Win)        │
│ • Extract post.py -> adapters/x.py                                     │
│ • Build adapters/bluesky.py with ATProto XRPC & RichText byte facets   │
│ • Add multi-platform toggles in config.json & due.py                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ PHASE 2: Zero-Dependency Visual Generator Pipeline                     │
│ • Build render/infocard.py (Pillow dark-mode 16:9 developer cards)     │
│ • Build render/carousel.py (HTML + CDP Page.printToPDF for carousels)  │
│ • Wire auto-attachments to X & Bluesky                                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ PHASE 3: LinkedIn CDP Automation Adapter                               │
│ • Build adapters/linkedin.py using CDP stealth session                 │
│ • Handle Quill/ProseMirror contenteditable input injection             │
│ • Automate PDF Document Carousel upload                                │
│ • Implement profile activity tab read-back verification                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ PHASE 4: Meta Threads Official API Adapter                             │
│ • Build adapters/threads.py with Graph API container flow              │
│ • Implement token management and refresh routines                      │
│ • Update Content Repurposer prompt matrix (1 insight -> 4 tones)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ PHASE 5: Unified Ledger & Cross-Platform Engagement Feedback           │
│ • Upgrade state.json to multi-target schema v2.0                       │
│ • Support independent platform retry on partial publishing failures    │
│ • Feed high-performing hooks back into references/voice-profile.md     │
└────────────────────────────────────────────────────────────────────────┘
```

### Phase 1 — Adapter Architecture & Bluesky Integration
* **Deliverables:**
  - Create `adapters/base.py` defining `PlatformAdapter`, `PlatformCapabilities`, `PublishPayload`, and `PublishResult`.
  - Refactor `scripts/post.py` internals into `adapters/x.py` implementing `PlatformAdapter` without altering CLI commands.
  - Implement `adapters/bluesky.py` using standard HTTP `urllib` calls for `createSession`, `uploadBlob`, and `createRecord`, including UTF-8 facet byte parsing.
  - Update `config.json` schema to include the `platforms` block.
  - Add unit tests for Bluesky facet calculations and session mock responses.
* **Exit Criteria:** A single command can post to X, Bluesky, or both simultaneously with independent verification.

### Phase 2 — Zero-Dependency Visual Pipeline
* **Deliverables:**
  - Implement `render/infocard.py`: turns research metrics into dark-mode 16:9 PNG cards.
  - Implement `render/carousel.py`: HTML + CDP `Page.printToPDF` generates multi-page slides.
  - Update `scripts/autoposter.py` to support automatic visual generation if `--visual` is passed.
* **Exit Criteria:** Generates crisp 1080x1080 multi-page PDF carousels and 16:9 infocards on Windows, macOS, and Linux without installing external binary dependencies.

### Phase 3 — LinkedIn CDP Adapter
* **Deliverables:**
  - Implement `adapters/linkedin.py` driving the dedicated browser profile.
  - Add selectors for post trigger button, ProseMirror editor, document upload modal, and submit button.
  - Implement read-back verification on `https://www.linkedin.com/in/{username}/recent-activity/all/`.
  - Enforce a 4-hour minimum spacing interval between LinkedIn posts.
* **Exit Criteria:** Automatically uploads a generated PDF carousel and long-form commentary to LinkedIn, verifies presence on the activity timeline, and saves a screenshot.

### Phase 4 — Meta Threads API & Content Repurposer
* **Deliverables:**
  - Implement `adapters/threads.py` with Meta Graph API container creation and publishing.
  - Build prompt templates for 1-insight-to-4-channel repurposing:
    * **X:** 270c, hook + insight + infocard.
    * **Bluesky:** 280c, open-source focus + facet links.
    * **LinkedIn:** 1,200c, problem + bulleted takeaways + PDF carousel.
    * **Threads:** 400c, conversational hook + open builder question.
* **Exit Criteria:** Daily planning generates 4 platform-tailored drafts from a single research item in one prompt cycle.

### Phase 5 — Unified Ledger & Feedback Loop
* **Deliverables:**
  - Update `state.json` to schema v2.0 with per-platform status tracking.
  - Upgrade `scripts/due.py mark` and `autoposter.py` to handle partial failures (e.g. if Bluesky succeeds but LinkedIn rate-limits, mark Bluesky done and retry only LinkedIn on the next tick).
  - Add engagement metrics scraper (`scripts/analytics.py`) to feed top-performing hook patterns back into voice profiling.
* **Exit Criteria:** Zero duplicate posts on partial network failure; automated metric logging across all enabled channels.

---

## 8. Multi-Platform Configuration Contract (`config.example.json` v2.0)

```json
{
  "_readme": "OmniPost V2 Multi-Platform Configuration",
  "timezone": "local",
  "slots": ["13:00", "16:00", "20:00", "00:00"],
  "jitter_minutes": 45,
  "min_gap_hours": 3,

  "platforms": {
    "x": {
      "enabled": true,
      "handle": "your_x_handle",
      "premium": false,
      "max_chars": 280
    },
    "bluesky": {
      "enabled": true,
      "identifier": "your_handle.bsky.social",
      "app_password_env": "BSKY_APP_PASSWORD"
    },
    "linkedin": {
      "enabled": false,
      "profile_id": "your_linkedin_slug",
      "min_gap_hours": 4
    },
    "threads": {
      "enabled": false,
      "user_id": "your_threads_user_id",
      "token_env": "THREADS_ACCESS_TOKEN"
    }
  },

  "browser": {
    "port": 9222,
    "profile_dir": "",
    "chrome_path": "",
    "headless": false
  },

  "subreddits": ["LocalLLaMA", "artificial", "singularity", "ChatGPTCoding"],
  "x_queries": ["AI agents", "AI coding", "developer tools"],
  "feeds": {
    "techcrunch-ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "hn-frontpage": "https://hnrss.org/frontpage?points=150"
  }
}
```

---

## 9. Security & Secret Management

* **Zero Plain-Text Secrets in JSON:** Passwords and OAuth tokens are never saved directly in `config.json`. The configuration accepts environment variable keys (`app_password_env`, `token_env`) or loads from a git-ignored `.env` file.
* **Isolated Browser Sessions:** Dedicated profile directories remain separated from everyday personal browsing sessions.
* **Immutable Failure Boundaries:** If any single platform adapter throws a fatal error, other platform publishers proceed uninterrupted, and the ledger isolates the failed platform for retrying.
