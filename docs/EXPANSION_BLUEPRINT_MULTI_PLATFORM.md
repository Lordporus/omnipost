# OmniPost: Multi-Platform Autonomous Publishing Pipeline
## Architectural Expansion Blueprint & Future Specification

---

## 1. Executive Summary & Core Philosophy

The core brilliance of **`tweetytweets`** is its refusal to pay predatory API fees (\$215+/month for X's basic tier) or rely on fragile, paid SaaS scrapers. Instead, it relies on a lean, anti-fragile engineering philosophy:

1. **Zero-Cost Open Intelligence:** Pulling news from open feeds (Hacker News Algolia API, Reddit JSON, RSS/Atom, and open web search).
2. **Native Browser Driving via CDP:** Direct Chrome DevTools Protocol over WebSockets with zero heavy frameworks (no Selenium, no Playwright).
3. **Refusal to Trust Toasts (Self-Verification):** Reading the profile timeline back is the *only* proof that a post actually published.
4. **Idle-is-Free Schedule Gate:** A deterministic cron gate that suppresses agent model calls when nothing is due, dropping running costs to pennies per month.
5. **Grounded Voice Calibration:** Profiling writing rhythm, beats, and hook patterns, then forcing every claim to cite a verified source article.

### The Objective of Version 2.0
Transform `tweetytweets` from a single-platform X bot into **`OmniPost`**: a unified, multi-platform publishing and verification engine that takes **one core research insight** and autonomously repurposes, formats, publishes, and verifies it across **LinkedIn, Bluesky, Threads, and Reddit**.

---

## 2. Current Architecture Deep-Dive: How It Interacts With X

Understanding the existing X integration reveals the design patterns to replicate:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          TWEETYTWEETS CORE ENGINE                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
     [RESEARCH.PY]             [DUE.PY]                 [POST.PY]
  HN / RSS / Reddit DOM      Jitter Gate             CDP WebSocket
  ~150 candidate items    Randomized minutes     Direct DevTools Protocol
                                    │                        │
                                    └───────────┬────────────┘
                                                ▼
                                    ┌───────────────────────┐
                                    │    REAL CHROME/EDGE   │
                                    │   PORT 9444 / CDP     │
                                    └───────────┬───────────┘
                                                ▼
                                    ┌───────────────────────┐
                                    │ 1. Focus ContentEd    │
                                    │ 2. Input.insertText   │
                                    │ 3. Click Post Button  │
                                    │ 4. Read Profile Back  │
                                    │ 5. Vision Screenshot  │
                                    └───────────────────────┘
```

### The Key Technical Mechanics:
* **The WebSocket Driver (`scripts/browser.py`):** Uses Python's native `websockets` library to send raw JSON-RPC messages to Chrome's HTTP debugging endpoint (`/json/version` and `/json/list`).
* **ContentEditable Injection (`Input.insertText`):** X's composer uses Draft.js/React. Modifying `element.innerText` or `innerHTML` bypasses React's virtual DOM state, leaving the Post button permanently disabled. The script sends raw keyboard input events (`Input.insertText`), which triggers React's internal state updates.
* **Profile Read-Back Verification (`scripts/post.py`):** Never trusts the green "Your post was sent" toast. It navigates to `https://x.com/{handle}`, parses `<article data-testid="tweet">` elements, matches text strings, and takes a viewport screenshot (`Page.captureScreenshot`).

---

## 3. Platform Expansion Feasibility Analysis

| Platform | Primary Access Method | API Cost | Bot Detection Risk | Optimal Content Format | Verification Method |
|---|---|---|---|---|---|
| **X (Twitter)** | Browser CDP | Free (bypasses \$215/mo) | Medium (Avoided via Jitter & Real Browser) | Short, punchy (280c) or long-form; visual infocards | Read back profile timeline DOM |
| **Bluesky** | **Native AT Protocol (XRPC)** | **100% Free** | **Near Zero** | 300 characters, rich facets, markdown links | Query profile via public ATProto API |
| **LinkedIn** | Browser CDP (or Official API) | API has restrictive partner tiers; CDP is \$0 | High (Aggressive session fingerprinting) | Deep-dive essays (1,000–3,000c), bullet points, **PDF Carousels** | Read back profile activity tab |
| **Threads (Meta)**| Hybrid (Official API or CDP) | Official API is Free (100 posts/day limit) | Low on API; Medium on CDP | 500 characters, conversational, image attachments | Query Threads API or profile DOM |
| **Reddit** | Free Script API / CDP | Free (OAuth script tier for personal bots) | High (Subreddit automods & spam filters) | Descriptive Title + Long markdown body + zero link spam | Read submitted posts via JSON API |

---

## 4. Deep-Dive on Target Platforms

### 1. Bluesky (The Easiest & Cleanest Win)
Unlike X, Bluesky is built on the open, decentralized **AT Protocol**. You do **not** need browser automation for Bluesky.
* **Authentication:** Generates an **App Password** from account settings (never exposes primary password).
* **Protocol:** Simple HTTP REST / XRPC endpoints (`com.atproto.server.createSession`, `com.atproto.repo.createRecord`).
* **Implementation:** Zero browser overhead. A 50-line Python module (`adapters/bluesky.py`) using `urllib.request`.
* **Limits:** 300 characters per post, automatic facet detection (mentions and links).

### 2. LinkedIn (The High-Value B2B Engine)
LinkedIn generates the highest organic reach for technical founders and solopreneurs, but official APIs require enterprise developer access or third-party paid proxies.
* **Automation Mechanism:** Browser CDP through the dedicated Edge/Chrome profile.
* **The Composer Problem:** LinkedIn uses a Quill/ProseMirror contenteditable editor (`div.ql-editor` or `div[role="textbox"]`). Just like X, it requires `Input.insertText`.
* **The Stealth Factor:** LinkedIn actively inspects `navigator.webdriver` and user-interaction patterns. 
  * *Required Safeguards:* Inject `Page.addScriptToEvaluateOnNewDocument` to mask automation indicators, add human-like keystroke delays (40–120ms), and enforce a minimum 4-hour gap between posts.
* **Superweapon: PDF Carousels:** LinkedIn algorithms heavily prioritize multi-page document carousels. Our pipeline can automatically render markdown slides into clean PDF cards via HTML/CSS-to-PDF (`weasyprint` or headless Chrome print).

### 3. Threads by Meta (Conversational Builder Hub)
In 2024, Meta officially opened the **Threads API** for all developers.
* **Mechanism:** Free official REST API (Graph API) with up to 100 posts per day per account.
* **Endpoints:**
  1. `POST /v1.0/{user-id}/threads` (creates media container with `text` and optional `image_url`).
  2. `POST /v1.0/{user-id}/threads_publish` (publishes the container).
* **Advantage:** Completely eliminates browser automation risks while keeping total cost at \$0.

### 4. Reddit (Community-Driven Deep Dives)
Automating Reddit requires strict etiquette to avoid subreddit bans.
* **Mechanism:** Reddit allows personal script bots under its free OAuth API tier (using the `praw` library or raw REST).
* **Content Rules:** Never post short marketing tweets. Posts must be structured as high-effort discussions:
  - Engaging, question-oriented title.
  - Multi-paragraph breakdown with technical trade-offs.
  - No external promotional links in the main post body.

---

## 5. Architectural Design of "OmniPost" (Version 2.0)

To support multi-platform without messy spaghetti code, the repository should adopt a **Hexagonal Adapter Pattern**:

```
                       ┌───────────────────────┐
                       │     RESEARCH ENGINE   │
                       │  (HN, RSS, Reddit)    │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │   CONTENT REPURPOSER  │
                       │   (LLM Voice Matrix)  │
                       └───────────┬───────────┘
                                   │
            ┌──────────────────────┴──────────────────────┐
            ▼                      ▼                      ▼
      [X Formatter]        [LinkedIn Formatter]   [Bluesky Formatter]
       280c + Hook          1,500c + Carousel        300c + Facets
            │                      │                      │
            ▼                      ▼                      ▼
      ┌───────────┐          ┌───────────┐          ┌───────────┐
      │ X Adapter │          │ LinkedIn  │          │  Bluesky  │
      │   (CDP)   │          │  Adapter  │          │  Adapter  │
      │           │          │   (CDP)   │          │ (ATProto) │
      └─────┬─────┘          └─────┬─────┘          └─────┬─────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   ▼
                       ┌───────────────────────┐
                       │   UNIFIED STATE &     │
                       │  VERIFICATION LEDGER  │
                       │     (state.json)      │
                       └───────────────────────┘
```

### Core Architecture Components:

#### 1. The `PlatformAdapter` Abstract Base Class
Every platform implements a uniform contract:
```python
class PlatformAdapter(ABC):
    @abstractmethod
    async def check_session(self) -> dict: ...

    @abstractmethod
    def max_characters(self) -> int: ...

    @abstractmethod
    async def publish(self, text: str, media_path: Path | None = None) -> dict: ...

    @abstractmethod
    async def verify_live(self, post_identifier: str) -> dict: ...
```

#### 2. The Content Repurposer (1 Insight $\rightarrow$ 4 Formats)
A single research discovery (e.g. an open-weight LLM breakthrough) gets formatted by the agent specifically for each channel:
* **X:** 270 characters, direct provocative hook, paired with a visual architecture card.
* **Bluesky:** 280 characters, technical insight, open-source focus.
* **LinkedIn:** 1,200 characters, first 2 lines as hook before "see more", structured with 4 bullet points, professional takeaway, and zero hashtags.
* **Threads:** 400 characters, casual builder tone, conversational question at the end.

#### 3. Automated Visual Pipeline (Infocards & PDF Carousels)
Visual posts get 3–5x more engagement across all platforms:
* **Infocard Generator:** Python script (using PIL or headless HTML render) that turns key bullet points into dark-mode 16:9 developer cards.
* **LinkedIn PDF Carousel Builder:** Generates 4–6 square slide images and binds them into a single PDF document for LinkedIn carousels.

---

## 6. Phased Implementation Roadmap

### Phase 1: Modularization & Bluesky Integration (Fastest ROI)
* Refactor `scripts/post.py` into `adapters/x.py`.
* Implement `adapters/bluesky.py` using direct AT Protocol HTTP requests (zero browser dependency, instant verification).
* Update `config.json` to allow enabling/disabling individual platform targets:
  ```json
  "platforms": {
    "x": { "enabled": true, "handle": "your_x_handle" },
    "bluesky": { "enabled": true, "identifier": "your_handle.bsky.social" }
  }
  ```

### Phase 2: LinkedIn CDP Engine & Visual Infocards
* Build `adapters/linkedin.py` driving the dedicated browser on port `9444`.
* Implement DOM selectors for LinkedIn's share modal (`div[role="textbox"]`, button selector, file uploader).
* Add `scripts/render_card.py` to programmatically generate dark-mode architecture cards and attach them automatically to both X and LinkedIn.

### Phase 3: Threads API Integration & Content Repurposer
* Implement `adapters/threads.py` using Meta's free official Threads API.
* Upgrade `scripts/due.py` to support multi-platform plans (`drafts/{date}.json` holding separate copies tailored for X, LinkedIn, and Threads).

### Phase 4: Unified Analytics & Feedback Loop
* Extend `state.json` to record cross-platform engagement metrics (impressions, retweets, LinkedIn reactions).
* Feed high-performing post structures back into `voice-profile.local.md` to automatically improve hook quality over time.
