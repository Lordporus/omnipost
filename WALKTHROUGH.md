# OmniPost V2.0: Architecture Walkthrough, Live Verification & Production Roadmap

**Document Date:** October 2026  
**Audience:** Operator & Developer  
**Status:** Verified Production & Multi-Platform Syndicate Operational  

---

## 1. Executive Summary: What Was `tweetytweets` vs What Became `OmniPost`

### The Baseline: `tweetytweets` (OmniPost V1.0)
Originally, this project was a specialized single-platform engine designed exclusively for **X (Twitter)**:
* **Monolithic Publishing:** A single script ([`scripts/post.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/post.py)) coupled browser automation, compose box detection, text injection, media attachment, and tweet verification into one continuous flow.
* **Browser Automation via CDP:** Automated Microsoft Edge on Windows via Chrome DevTools Protocol (CDP) on port `9444` using the user data directory `C:\Users\Sachin\.tweetytweets\edge-profile`.
* **Single Content Format:** Plain text posts strictly constrained by the measured character ceiling (280 characters for free-tier accounts).
* **Schedule Gatekeeper:** A cron monitor ([`scripts/due.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/due.py)) managing jittered time slots (`13:00`, `16:00`, `20:00`, `00:00`) with an incremental `.tick` counter.
* **Voice Profiling:** Static heuristic extraction from user-provided top tweets ([`scripts/voice_profile.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/voice_profile.py)) outputting to `references/voice-profile.local.md`.
* **Single-Target Ledger:** `state.json` stored records with top-level `tweet_url`, `verified: true`, and X-specific timestamps.

---

### The Evolution: `OmniPost` (V2.0 Multi-Platform Syndicate)
Over Phases 1 through 5, we re-architected the entire foundation into an extensible, multi-network publishing syndicate:

```
                               ┌────────────────────────────────────────┐
                               │           OmniPost V2.0 Core           │
                               │  Research ➔ Repurpose ➔ Schedule Gate  │
                               └───────────────────┬────────────────────┘
                                                   │
            ┌──────────────────────┬───────────────┴──────────────┬──────────────────────┐
            ▼                      ▼                              ▼                      ▼
   ┌─────────────────┐    ┌─────────────────┐            ┌─────────────────┐    ┌─────────────────┐
   │    adapters/    │    │    adapters/    │            │    adapters/    │    │    adapters/    │
   │      x.py       │    │   bluesky.py    │            │   linkedin.py   │    │   threads.py    │
   └────────┬────────┘    └────────┬────────┘            └────────┬────────┘    └────────┬────────┘
            │                      │                              │                      │
       Stealth CDP            ATProto XRPC                   Stealth CDP            Stealth CDP
       (x.com/compose)     (Zero-browser API)            (ProseMirror & PDF)    (Zero-cloud upload)
            │                      │                              │                      │
            └──────────────────────┴───────────────┬──────────────┴──────────────────────┘
                                                   │
                                                   ▼
                                      ┌─────────────────────────┐
                                      │    scripts/ledger.py    │
                                      │     state.json v2.0     │
                                      │ Partial-Failure Retries │
                                      └─────────────────────────┘
```

#### What Was Added Across Phases 1–5:
1. **Phase 1 — Universal Adapter Abstraction & Bluesky:**
   * [`adapters/base.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/base.py): Standard contracts (`PlatformAdapter`, `PlatformCapabilities`, `PublishPayload`, `PublishResult`).
   * [`adapters/x.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/x.py): Extracted X logic preserving existing CDP automation.
   * [`adapters/bluesky.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/bluesky.py): Lightweight, zero-browser publishing over ATProto XRPC with UTF-8 byte slice facet parsing for URLs and mentions.
2. **Phase 2 — Zero-Dependency Visual Pipeline:**
   * [`render/infocard.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/render/infocard.py): Generates dark-mode 16:9 PNG cards (1200x675) using pure Python Pillow without C-library dependencies.
   * [`render/carousel.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/render/carousel.py): Generates 1080x1080 multi-slide PDF carousels using HTML templates and headless CDP `Page.printToPDF`.
3. **Phase 3 — LinkedIn CDP Adapter:**
   * [`adapters/linkedin.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/linkedin.py): Stealth browser session targeting LinkedIn's ProseMirror/TipTap editor, multi-page PDF document carousel upload, 4-hour rate limit guardrails, and activity feed read-back verification.
4. **Phase 4 — Meta Threads CDP Adapter & Polymorphic Repurposer:**
   * [`adapters/threads.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/threads.py): 100% browser CDP automation bypassing Meta Graph API (eliminating cloud image hosting costs, directly attaching local images via `DOM.setFileInputFiles`).
   * [`scripts/repurpose.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/repurpose.py): 1 research insight $\rightarrow$ 4 platform-tailored drafts:
     * **X:** 280c punchy contrarian hook.
     * **Bluesky:** 300c conversational tech discussion with rich facets.
     * **LinkedIn:** 1,500c leadership narrative + PDF carousel.
     * **Threads:** 500c builder discussion + infocard image.
   * [`scripts/autoposter.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/autoposter.py): Dispatches platform-tailored text and media per network.
5. **Phase 5 — Unified Ledger & Closed-Loop Feedback:**
   * [`scripts/ledger.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/ledger.py): Schema v2.0 with atomic crash-safe writes, legacy auto-migration, and per-platform status tracking.
   * **Partial-Failure Isolation:** If 1 platform fails (e.g. LinkedIn cooldown), successful channels are skipped (`[SKIP]`) and only failed ones are retried on the next tick with zero duplicate posts.
   * [`scripts/analytics.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/analytics.py): \$0 metrics collection via ATProto XRPC and X syndication/CDP.
   * [`scripts/feedback.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/feedback.py): Algorithmic hook classification and closed-loop updating of `references/voice-profile.local.md`.

---

## 2. The Live Verification Reality: Proof of Publishing Across All 4 Networks

> [!IMPORTANT]
> **Real-World Live Status: 100% Operational & Verified.**  
> In our live production run, the system executed a synchronous multi-network publishing blast with post verification across all four social networks on live production servers.

### Live Publication Record (Test Blast Verification)
* **Message Published:** *"OmniPost V2 live test: multi-platform sync active across X, Bluesky, LinkedIn, and Threads."*
* **Date & Timestamp:** October 5, 2026 — 19:46 IST

| Platform | Authentication | Result | Verification Status & Live URL |
| :--- | :--- | :---: | :--- |
| **X (Twitter)** | Stealth Browser CDP | **SUCCESS** | Verified live via profile read-back.<br>[View Live Tweet](https://x.com/Lordporus/status/2107106701006827729) |
| **Bluesky** | ATProto XRPC | **SUCCESS** | Verified live via ATProto record query.<br>[View Live Post](https://bsky.app/profile/lordporus.bsky.social/post/3mx52tye73a2t) |
| **LinkedIn** | Stealth Browser CDP | **SUCCESS** | Verified live via feed toast & activity URN.<br>[View Live Update](https://www.linkedin.com/feed/update/urn:li:activity:7512874289356771328/) |
| **Meta Threads** | Stealth Browser CDP | **SUCCESS** | Verified live via profile feed check.<br>[View Live Profile](https://www.threads.com/@ig_lordporus) |

---

## 3. Engineering Solutions Discovered & Hardened During Live Testing

During real-world live testing, we discovered and permanently resolved critical platform quirks:

### 1. LinkedIn DOM Migration (Quill $\rightarrow$ TipTap/ProseMirror)
* **Issue Discovered:** LinkedIn completely restructured their feed composer DOM. The previous `ql-editor` and simple button selectors failed to register clicks or accept text injections. The "Start a post" button is now a `div role="button"` containing child text spans.
* **The Fix in [`adapters/linkedin.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/linkedin.py):**
  * Implemented native coordinate mouse clicking (`Input.dispatchMouseEvent`) targeting the exact bounding box of the compose trigger.
  * Updated editor detection to target modern ProseMirror (`div.tiptap.ProseMirror`, `div[role="textbox"]`).
  * Added composer hydration polling with timeout safety to ensure the modal is fully mounted before text injection.

### 2. Threads Domain Redirection & Lexical State Tree
* **Issue Discovered:** Meta now actively redirects `threads.net` to `threads.com`. The redirect was causing CDP WebSocket frame drops. Additionally, Threads uses Meta's Lexical rich text engine; programmatic text injection failed to enable the "Post" button unless the editor DOM received a genuine native cursor focus event.
* **The Fix in [`adapters/threads.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/threads.py):**
  * Updated all target URLs to `threads.com`.
  * Fixed username resolution to strip leading `@` symbols when constructing profile URLs.
  * Added CDP native mouse click inside the Lexical container before injecting text via `Input.insertText`, followed by bounding box click dispatch on the Post button.

### 3. Edge Browser Tab Duplication & Memory Throttling
* **Issue Discovered:** Microsoft Edge was spawning a new tab on each CDP adapter call without terminating background targets. After multiple checks, 15+ background tabs accumulated, triggering Edge's background tab sleeping/throttling mechanism which caused DOM evaluate calls to hang indefinitely.
* **The Fix in [`scripts/browser.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/browser.py):**
  * Enhanced `Session.open_page()` to inspect `list_tabs()` for existing tabs matching the destination domain before creating a new target.
  * Existing domain tabs are brought to the front (`Target.activateTarget`) and reused, preventing memory bloat and tab suspension.

### 4. Direct App Password Support in Bluesky
* **Issue Discovered:** The Bluesky adapter originally required `BSKY_APP_PASSWORD` exclusively from system environment variables.
* **The Fix in [`adapters/bluesky.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/bluesky.py):**
  * Added defensive credential resolution: checks `app_password` in `config.json` directly, falls back to `app_password_env`, and finally system environment variables.

### 5. On-Demand Immediate Publishing Tool
* **Created [`scripts/publish_now.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/publish_now.py):**
  * Added a dedicated CLI tool to instantly broadcast messages or media across any combination of platforms (e.g. `python scripts/publish_now.py --text "..." --platforms x,bluesky,linkedin,threads`).

---

## 4. Current State: Architecture & Unified Ledger

All four platform configurations are fully stored and operational in [`config.json`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/config.json):
```json
  "platforms": {
    "x": {
      "enabled": true,
      "handle": "Lordporus",
      "premium": false,
      "max_chars": 280
    },
    "bluesky": {
      "enabled": true,
      "identifier": "lordporus.bsky.social",
      "app_password": "..."
    },
    "linkedin": {
      "enabled": true,
      "profile_url": "www.linkedin.com/in/purushottam-kumar-773a59219",
      "min_gap_hours": 4
    },
    "threads": {
      "enabled": true,
      "handle": "@ig_lordporus"
    }
  }
```

The unified ledger ([`scripts/ledger.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/ledger.py)) records state atomically to `state.json` with per-platform status tracking:
```json
{
  "schema_version": 2,
  "slots": {
    "2026-10-05": {
      "live_test": {
        "x": {"status": "success", "verified": true, "url": "https://x.com/Lordporus/status/2107106701006827729"},
        "bluesky": {"status": "success", "verified": true, "url": "https://bsky.app/profile/lordporus.bsky.social/post/3mx52tye73a2t"},
        "linkedin": {"status": "success", "verified": true, "url": "https://www.linkedin.com/feed/update/urn:li:activity:7512874289356771328/"},
        "threads": {"status": "success", "verified": true, "url": "https://www.threads.com/@ig_lordporus"}
      }
    }
  }
}
```

---

## 5. The Autonomous Gap: What Remains to Run 100% Unattended

Now that the publishing adapters work reliably in live conditions, the final step to make OmniPost a **fully autonomous product** operating entirely on your behalf requires closing five automation loops:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE UNATTENDED AUTONOMOUS ROADMAP                    │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Edge Browser Lifecycle Daemon (Self-Healing Background Process)     │
│    • Windows auto-launch on reboot / wake from sleep                   │
│    • Health check ensuring port 9444 is alive and responsive           │
├────────────────────────────────────────────────────────────────────────┤
│ 2. Automated Daily Content Generation Engine                           │
│    • Morning research harvest (HN, RSS, TechCrunch, ArXiv)            │
│    • Automated topic synthesis & voice profiling (voice-profile.local) │
│    • Polymorphic formatting (X hook, Bsky tech, LI carousel, Threads) │
├────────────────────────────────────────────────────────────────────────┤
│ 3. Automated Daily Plan Population                                     │
│    • Automatically populate drafts/YYYY-MM-DD.json at midnight         │
│    • Ensure every jittered slot has tailored text and visual assets    │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Unattended Windows Task Scheduler Integration                       │
│    • Task 1: Daily Pipeline at 11:00 AM (Research + Repurpose)         │
│    • Task 2: Cron Gatekeeper every 10 mins (Autoposter execution)      │
├────────────────────────────────────────────────────────────────────────┤
│ 5. Notification Dispatcher & Nightly Analytics Sync                    │
│    • Windows Toast notifications / log alerts on successful publish    │
│    • Nightly metrics harvest + voice profile self-adaptation           │
└────────────────────────────────────────────────────────────────────────┘
```

The detailed, task-by-task engineering blueprint to implement this autonomous layer is defined in [`PRODUCTION_SCHEDULE_PLAN.md`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/PRODUCTION_SCHEDULE_PLAN.md).
