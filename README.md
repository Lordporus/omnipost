# OmniPost

**An autonomous X/Twitter publishing pipeline for AI agents.**

OmniPost is a lean, cost-efficient publishing and verification engine for X (Twitter). It researches the day's discussions in your domain, drafts posts aligned with your personal writing voice, publishes via a real authenticated browser session, and cryptographically/visually verifies that each post went live on your profile timeline.

- **Zero API Costs:** Bypasses X's \$215+/month developer tier by driving a dedicated, authenticated browser session over Chrome DevTools Protocol (CDP).
- **Free Intelligence Gathering:** Collects and ranks insights using free, open endpoints (Hacker News Algolia API, RSS/Atom feeds, Reddit rendered DOM, and X search).
- **Single Core Dependency:** Built with Python standard library plus `websockets`. No Playwright, Puppeteer, or Selenium overhead.
- **Closed-Loop Verification:** Refuses to trust success toasts. Reads back profile DOM and captures viewport vision screenshots before marking slots complete.
- **Idle Is Free:** Deterministic schedule gate prevents costly recurring LLM calls when no slot is due.

```
       ┌──────────┐   ┌────────┐   ┌───────────┐   ┌─────────┐   ┌────────┐
 11:00 │ RESEARCH │ → │  PLAN  │ → │ SCHEDULE  │ → │ PUBLISH │ → │ VERIFY │
       └──────────┘   └────────┘   └───────────┘   └─────────┘   └────────┘
        HN, RSS,       agent        cron gate        real          read the
        Reddit, X      writes 4     wakes only       browser       profile
        ~150 items     drafts       when due         composer      back
```

---

## Current V1 Status

OmniPost **v1.0.0** is focused exclusively on a reliable, autonomous **X (Twitter)** publishing pipeline.

- **Status:** Production-ready for single-account autonomous X publishing.
- **Scope:** Complete end-to-end flow from research aggregation through profile read-back verification.
- **Future:** Serves as the foundation for multi-platform OmniPost V2 (Bluesky, LinkedIn, Threads, Reddit). Multi-platform adapters are part of the future roadmap and are **not** active in V1.

---

## Table of Contents

- [What It Actually Does](#what-it-actually-does)
- [Architecture & Workflow](#architecture--workflow)
- [Verified Feature Set](#verified-feature-set)
- [Requirements](#requirements)
- [Installation & Quickstart](#installation--quickstart)
- [Configuration Reference](#configuration-reference)
- [First-Time Setup & Onboarding](#first-time-setup--onboarding)
- [CLI Usage](#cli-usage)
- [Scheduling & Automation](#scheduling--automation)
- [Verification & Trust Boundaries](#verification--trust-boundaries)
- [Guardrails](#guardrails)
- [Security & Privacy](#security--privacy)
- [Known Limitations & Risks](#known-limitations--risks)
- [Troubleshooting](#troubleshooting)
- [Origin and Attribution](#origin-and-attribution)
- [What Changed in This Version](#what-changed-in-this-version)
- [Project Evolution](#project-evolution)
- [OmniPost V2 Roadmap](#omnipost-v2-roadmap)
- [License](#license)

---

## What It Actually Does

Every day, unattended:

| Stage | Action |
|---|---|
| **Research** | Gathers candidate items from Hacker News (Algolia API), RSS feeds, Reddit rendered DOM, and X search; normalizes, deduplicates, and ranks by engagement. |
| **Plan** | Your AI agent inspects candidate stories, reviews source links, and produces post drafts strictly tuned to your measured voice profile. |
| **Schedule** | Generates jittered daily slots (default: 4 slots). A monitor script checks slot eligibility; when idle, it emits `IDLE` so zero LLM tokens are consumed. |
| **Publish** | Types text into X's contenteditable composer via CDP `Input.insertText` (triggering React state changes), optionally attaches media, and submits. |
| **Verify** | Polls your public profile timeline to locate the published text, captures a viewport screenshot, and validates the live status URL before closing the slot. |

---

## Architecture & Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          OMNIPOST V1 CORE ENGINE                       │
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
                                    │ REAL CHROME / EDGE    │
                                    │ Port 9222 / 9444 CDP  │
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

1. **Direct DevTools Protocol (`scripts/browser.py`):** Speaks raw JSON-RPC over WebSockets to Chrome/Edge's `/json/version` and `/json/list` endpoints. No third-party browser automation frameworks.
2. **Synthetic Input Simulation (`scripts/post.py`):** Uses Chrome DevTools Protocol `Input.insertText` rather than `element.innerText`, ensuring Draft.js/React internal state updates and enabling the Post button.
3. **Double Verification:** Combines DOM timeline parsing (`article[data-testid="tweet"]`) with viewport screenshot capture (`Page.captureScreenshot`).

---

## Verified Feature Set

Every feature listed below is verified in the codebase:

- **Hacker News Collector:** Algolia API queries with point thresholds and age filtering.
- **RSS/Atom Feed Parser:** Zero-dependency standard library parser for arbitrary RSS and Atom feeds.
- **Reddit DOM Scraper:** Headless browser extraction of top posts from configured subreddits.
- **X Search Scraper:** DOM extraction of high-engagement discussions across specified search queries.
- **Jitter Scheduling:** Randomized distribution around anchor slots with minimum spacing constraints.
- **Idle-is-Free Gate:** Emits byte-identical `IDLE` output during inactive periods to suppress scheduler invocations.
- **Browser Port Auto-Detection:** Discovers Chrome, Chromium, and Microsoft Edge across Windows, macOS, and Linux.
- **Dynamic Character Limit Probe:** Empirically probes composer boundaries (280 vs. Premium expanded tiers) without publishing.
- **Strict Account Guard:** Halts immediately if the signed-in session handle does not match `config.json`.
- **Length Enforcer:** Validates character count at draft creation and publishing time (reserving space for AI update headers).
- **Profile Read-Back Verification:** Polls profile feed for exact text match and resolves the live `https://x.com/{handle}/status/{id}` URL.
- **Readiness Doctor:** Audits Python runtime, dependencies, configuration, browser binaries, writable directories, and live sessions.
- **Statistical Voice Profiler:** Computes length distribution, beat cadence, devices (emoji, hashtags, links, numbers), and opening hook patterns from sample posts.
- **Automated Runner (`scripts/autoposter.py`):** CLI orchestrator that checks slots, publishes, verifies, and records outcomes in one atomic pass.

---

## Requirements

- **Python:** 3.10 or newer (tested on 3.11).
- **Browser:** Google Chrome, Chromium, or Microsoft Edge installed.
- **X Account:** Logged in within the dedicated browser profile.
- **Dependencies:** Listed in `requirements.txt` (`websockets>=12.0`).

---

## Installation & Quickstart

### 1. Clone & Install

```bash
git clone https://github.com/your-username/omnipost.git
cd omnipost
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.json config.json
python scripts/doctor.py
```

### 3. Launch Automation Browser & Sign In

```bash
python scripts/browser.py launch
```

A dedicated browser window will launch. Navigate to `https://x.com/login` and sign into your X account.
*Note: Use "Email or username", not Google OAuth sign-in, to ensure the correct account profile is maintained.*

### 4. Verify Session & Measure Limits

```bash
python scripts/post.py check          # verifies active session handle
python scripts/post.py measure --save # tests composer ceiling and persists it
python scripts/post.py limits         # inspects verified character limits
```

---

## Configuration Reference

Edit `config.json` (git-ignored for privacy):

```json
{
  "handle": "your_x_handle",
  "premium": false,
  "max_chars": 280,
  "max_chars_verified": true,
  "timezone": "local",
  "slots": ["13:00", "16:00", "20:00", "00:00"],
  "jitter_minutes": 45,
  "min_gap_hours": 3,
  "ai_update_enabled": true,
  "ai_update_slot": "16:00",
  "ai_update_header": "Daily AI updates | Day {day}",
  "research_hour": 11,
  "window_hours": 36,
  "subreddits": ["LocalLLaMA", "artificial", "singularity", "ChatGPTCoding"],
  "x_queries": ["AI agents", "AI coding", "developer tools"],
  "feeds": {
    "techcrunch-ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "hn-frontpage": "https://hnrss.org/frontpage?points=150"
  },
  "require_verified_source": true,
  "browser": {
    "port": 9222,
    "profile_dir": "",
    "chrome_path": "",
    "headless": false
  }
}
```

| Key | Description |
|---|---|
| `handle` | Account handle without `@`. Guard halts if browser session does not match. |
| `premium` | Boolean indicating X Premium tier. Determined via `post.py measure --save`. |
| `max_chars` | Character ceiling enforced on all drafts. |
| `max_chars_verified` | Boolean marker set when character limit is measured live. |
| `slots` | Daily anchor times in HH:MM format. |
| `jitter_minutes` | Maximum window offset applied to each slot. |
| `min_gap_hours` | Minimum spacing enforced between scheduled slots. |
| `ai_update_enabled` | Enables automated day counter on designated slot. |
| `browser.port` | Remote debugging port (default: 9222; 9444 supported for Edge). |
| `browser.profile_dir` | Path to persistent browser profile (default: `~/.omnipost/chrome-profile`). |

---

## First-Time Setup & Onboarding

### Voice Profile Extraction

To prevent generic outputs, OmniPost calibrates writing style using your existing posts:

1. Save 5–20 of your top posts into `scratch/my_top_tweets.txt` (separated by `---`).
2. Run the analyzer:
   ```bash
   python scripts/voice_profile.py --in scratch/my_top_tweets.txt
   ```
3. Copy the output into `references/voice-profile.local.md` (git-ignored).
4. Every post planned by an agent or script must follow the patterns in this file.

---

## CLI Usage

### Research

```bash
# Gather candidates from all configured sources for the last 36 hours
python scripts/research.py collect --hours 36

# Inspect feed health
python scripts/research.py sources

# Test individual sources
python scripts/research.py hn --points 100 --limit 10
python scripts/research.py reddit LocalLLaMA --limit 5
python scripts/research.py x "AI agents" --limit 5
```

### Planning & Scheduling

```bash
# Generate today's jittered schedule (saved to drafts/YYYY-MM-DD.json)
python scripts/due.py make-plan

# View current slots and status
python scripts/due.py show

# Check if a slot is currently due (emits JSON or IDLE)
python scripts/due.py check

# Populate a slot with draft text
python scripts/due.py fill --slot 13:00 --file scratch/draft1.txt

# Manually mark a slot as posted
python scripts/due.py mark --slot 13:00 --url "https://x.com/yourhandle/status/123"
```

### Publishing & Verification

```bash
# Dry run: populates the composer and captures shots/compose.png without posting
python scripts/post.py compose --text "Testing OmniPost" --dry-run

# Publish draft
python scripts/post.py post --text-file scratch/draft1.txt

# Publish daily roundup (appends dynamic day counter)
python scripts/post.py post --text-file scratch/draft_ai.txt --kind ai_update

# Read back recent posts from profile
python scripts/post.py verify

# View ledger status
python scripts/post.py status
```

### Autonomous Single-Command Execution

```bash
# Check due slot, publish, verify, and mark in one atomic pass
python scripts/autoposter.py

# Dry-run check without publishing
python scripts/autoposter.py --dry-run
```

---

## Scheduling & Automation

OmniPost uses a **deterministic gate**: the scheduler runs a lightweight script rather than invoking an LLM.

### 1. Plain Cron

```cron
# 11:00 AM - Gather research material
0 11 * * * cd /path/to/omnipost && python scripts/research.py collect --hours 36

# Every 10 minutes - Check for due posts; silent when IDLE
*/10 * * * * cd /path/to/omnipost && python scripts/autoposter.py >> /var/log/omnipost.log 2>&1
```

### 2. Hermes Agent / AI Agent Monitor

```
name:      x-autopost
schedule:  every 10m
monitor:   omnipost_due.py
deliver:   origin
```

*When `due.py check` emits `IDLE`, unchanged output suppresses the agent invocation entirely. Idle ticks cost \$0.*

### 3. Windows Task Scheduler

```powershell
schtasks /Create /SC MINUTE /MO 10 /TN "OmniPost Runner" `
  /TR "cmd /c cd /d C:\path\to\omnipost && python scripts\autoposter.py"
```

---

## Verification & Trust Boundaries

OmniPost adheres to a strict verification policy:

1. **Never trust toasts:** Browser UI toasts like *"Your post was sent"* can fire even when backend rate limiting or content filtering drops the post.
2. **Profile timeline polling:** The script navigates to `https://x.com/{handle}`, parses the DOM for matching text, and resolves the actual tweet status URL.
3. **Timeline caching tolerance:** Profile timelines can display stale renders for up to 30–60 seconds after submission. The verifier polls with backoff before concluding failure.
4. **Vision checks:** Viewport screenshots (`shots/profile.png` and `shots/compose.png`) provide visual confirmation of layout, line breaks, and image cards.

---

## Guardrails

- **Account Mismatch Guard:** Halts immediately if the browser profile's active handle does not match `config.handle`.
- **Character Limit Guard:** Blocks drafts exceeding measured ceilings before submission.
- **Stale Slot Retirement:** Slots more than 6 hours overdue are marked skipped rather than posted late.
- **Retry Bounds:** Failed attempts are capped at 2 tries to avoid duplicate posts.
- **Source Verification:** Mandates that every post claim traces back to a verified research link.

---

## Security & Privacy

- **No Stored Passwords:** Authentication state remains exclusively within your local browser profile (`~/.omnipost/chrome-profile`).
- **No Committed Secrets:** `config.json`, `state.json`, `.tick`, and all draft files are excluded via `.gitignore`.
- **Private Voice Profile:** `references/voice-profile.local.md` is strictly git-ignored so personal writing data is never published.
- **Sanitized Examples:** `config.example.json` contains no tokens or credentials.

---

## Known Limitations & Risks

- **Platform Rules:** Automating actions via browser sessions without the official API carries inherent account risk under X's platform policies. Pacing and jitter are designed to minimize detection.
- **DOM Fragility:** X periodically updates DOM attributes and class selectors. If posting or verification stalls, run `python scripts/doctor.py --live` to inspect element targeting.
- **Headless Mode Nuances:** Certain bot protection layers detect `--headless` flags. Running with visible browser windows (`headless: false`) provides maximum reliability.

---

## Troubleshooting

| Issue | Cause | Resolution |
|---|---|---|
| `not logged in` | Browser profile lacks active session | Run `python scripts/browser.py launch`, log in manually, then rerun `post.py check`. |
| `WRONG ACCOUNT` | Logged-in handle does not match `config.json` | Log into the intended account or update `config.json`. |
| Post button remains disabled | Text exceeds limit or React state did not update | Run `python scripts/post.py compose --dry-run` to inspect `shots/compose.png`. |
| `verified: false` | Profile timeline render delayed | Run `python scripts/post.py verify` manually after 30 seconds. |
| Browser fails to launch | Incorrect path or conflicting instance | Set `browser.chrome_path` in `config.json` or check task manager for zombie processes. |
| Port connection refused | Debugging port not open | Ensure browser was started with `--remote-debugging-port=9222` (or 9444). |

---

## Origin and Attribution

This project began as a derivative of the MIT-licensed [tweetytweets](https://github.com/vedantdhande04/tweetytweets) project originally authored by Vedant Dhande (`vedantdhande04`).

The original MIT license and copyright notice (`Copyright (c) 2026 tweetytweets contributors`) are preserved in full in [LICENSE](file:///LICENSE).

---

## What Changed in This Version

This repository represents the **OmniPost V1.0.0** release, incorporating enhancements, fixes, and architectural preparation:

1. **Windows & Microsoft Edge Compatibility:**
   - Added `--remote-allow-origins=*` flag to CDP launch parameters for Chromium 111+ compliance.
   - Added `--disable-background-mode` to prevent background browser processes from intercepting debug ports.
   - Refined Windows process detachment flags (`CREATE_NEW_PROCESS_GROUP`) for stable detached launches.
   - Added automated Edge auto-detection and helper launch scripts (`launch_edge.bat`).
2. **Composer Error Detection Enhancement:**
   - Replaced broad full-body error text scanning in `post.py` with targeted DOM parsing of modal headers and toast alerts, eliminating false positive errors.
3. **Autonomous End-to-End Runner:**
   - Implemented `scripts/autoposter.py` for unattended slot planning, checking, posting, and verification with safety guards.
4. **Automated Test Suite:**
   - Added zero-dependency unit tests (`tests/test_omnipost.py`) covering settings, due calculations, research deduplication, and voice profiling.
5. **Security & Privacy Hardening:**
   - Sanitized configuration examples and expansion blueprints to ensure no local paths or handles are exposed.
   - Expanded `.gitignore` coverage to protect Edge profiles, debug logs, and test artifacts.
6. **Rebranding & V2 Foundations:**
   - Rebranded public interface to OmniPost while maintaining full backwards compatibility for existing installations.
   - Authored the comprehensive multi-platform architectural blueprint in `docs/EXPANSION_BLUEPRINT_MULTI_PLATFORM.md`.

---

## Project Evolution

### Upstream (tweetytweets)
Created by Vedant Dhande as an autonomous X publishing pipeline utilizing direct Chrome DevTools Protocol over WebSockets without paid API fees.

### V1 (OmniPost V1.0.0)
Our current release hardens the X pipeline for production use, resolves Windows/Edge compatibility challenges, adds test coverage, provides autonomous runner tooling, and establishes a clean open-source foundation.

### V2 (OmniPost Multi-Platform)
The planned next generation will decouple the publishing engine into platform adapters, repurposing a single research discovery across multiple platforms.

---

## OmniPost V2 Roadmap

The future multi-platform architecture is documented in [EXPANSION_BLUEPRINT_MULTI_PLATFORM.md](file:///docs/EXPANSION_BLUEPRINT_MULTI_PLATFORM.md).

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

### Planned Milestones:

- **Phase 1 — Modularization & Bluesky:**
  - Decouple `post.py` into `adapters/x.py`.
  - Implement native AT Protocol integration (`adapters/bluesky.py`) with zero browser overhead.
  - Add per-platform toggle configuration in `config.json`.
- **Phase 2 — LinkedIn & Visual Infocards:**
  - Build `adapters/linkedin.py` driving CDP with Quill/ProseMirror editor compatibility.
  - Implement programmatic infocard rendering and multi-page PDF carousel generation.
- **Phase 3 — Threads & Multi-Platform Repurposing:**
  - Implement Meta Threads official API adapter (`adapters/threads.py`).
  - Upgrade `due.py` to support synchronized multi-platform publishing schedules.
- **Phase 4 — Unified Analytics & Feedback Loop:**
  - Cross-platform engagement aggregation.
  - Closed-loop optimization feeding top metrics back into voice profiling.

---

## License

MIT License — see [LICENSE](file:///LICENSE).
Preserves original copyright notice `Copyright (c) 2026 tweetytweets contributors` and `Copyright (c) 2026 OmniPost contributors`.
