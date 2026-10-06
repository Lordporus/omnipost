# OmniPost V2.0: Architecture Walkthrough, Live Verification & Production Guide

**Document Date:** October 2026  
**Audience:** Operators, DevOps Engineers, and AI System Architects  
**Status:** 100% Implemented, Verified & Production Sealed across X, Bluesky, LinkedIn, and Meta Threads  

---

## 1. Executive Summary: What Was `tweetytweets` vs What Became `OmniPost`

### The Baseline: `tweetytweets` (OmniPost V1.0)
Originally, this project was a specialized single-platform engine designed exclusively for **X (Twitter)**:
* **Monolithic Publishing:** A single script ([`scripts/post.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/post.py)) coupled browser automation, compose box detection, text injection, media attachment, and tweet verification into one continuous flow.
* **Browser Automation via CDP:** Automated Microsoft Edge on Windows via Chrome DevTools Protocol (CDP) on port `9444` using the user data directory `C:\Users\Sachin\.tweetytweets\edge-profile`.
* **Single Content Format:** Plain text posts strictly constrained by the measured character ceiling (280 characters for free-tier accounts).
* **Schedule Gatekeeper:** A cron monitor ([`scripts/due.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/due.py)) managing jittered time slots (`13:00`, `16:00`, `20:00`, `00:00`).
* **Single-Target Ledger:** `state.json` stored records with top-level `tweet_url`, `verified: true`, and X-specific timestamps.

---

### The Evolution: `OmniPost` (V2.0 Multi-Platform Sovereign Syndicate)
Over Phases 1 through 5 of `PRODUCTION_SCHEDULE_PLAN.md` and Phases 1 through 6 of `ONBOARDING_DEPLOYMENT_EXECUTION_PLAN.md`, we transformed the codebase into an autonomous, sovereign publishing syndicate:

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
    (x.com/compose)        (Zero-browser API)            (TipTap/ProseMirror    (Direct File Input
                                                          & Vector Carousel)     Zero-Cloud Upload)
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

#### What Was Added:
1. **Universal Platform Adapters:**
   * [`adapters/base.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/base.py): Unified contracts (`PlatformAdapter`, `PlatformCapabilities`, `PublishPayload`, `PublishResult`).
   * [`adapters/x.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/x.py): Stealth CDP automation targeting X compose workflow.
   * [`adapters/bluesky.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/bluesky.py): Zero-browser direct ATProto XRPC engine with UTF-8 byte facet parsing for links and mentions.
   * [`adapters/linkedin.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/linkedin.py): Stealth CDP session targeting modern TipTap/ProseMirror DOM, document carousel uploading, and activity URN read-back verification.
   * [`adapters/threads.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/adapters/threads.py): Direct CDP automation for Meta Threads bypassing Graph API and cloud storage fees.
2. **Zero-Dependency Visual Rendering Engine:**
   * [`render/infocard.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/render/infocard.py): Renders 16:9 dark-mode programmatic PNG cards via Pillow.
   * [`render/carousel.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/render/carousel.py) & [`render/template.html`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/render/template.html): Modern dark-tech 1080x1080 HTML/PDF carousel generator producing vector-sharp document carousels.
3. **Autonomous Scheduling & Orchestration:**
   * [`scripts/browser_daemon.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/browser_daemon.py): Auto-heals CDP port 9444, appending container & Linux sandbox flags (`--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`).
   * [`scripts/generate.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/generate.py): Daily topic extraction and polymorphic synthesis.
   * [`scripts/pipeline.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/pipeline.py): End-to-end autonomous morning pipeline orchestrator.
   * [`scripts/daemon.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/daemon.py): Standalone continuous background runner.
   * [`scripts/setup_scheduler.ps1`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/setup_scheduler.ps1): Native Windows Task Scheduler installer.
4. **Desktop & Remote Alerting:**
   * [`scripts/notify.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/notify.py): Windows native PowerShell Toast notifications.
   * [`scripts/notify_webhook.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/notify_webhook.py): Headless Telegram Bot & Discord Webhook dispatcher with fast-fail session expiry alerts.
5. **Zero-Friction Onboarding & Deployment:**
   * [`setup.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/setup.py) & [`scripts/wizard.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/wizard.py): 6-step interactive CLI onboarding wizard with `--non-interactive` CI fallback.
   * [`scripts/validator.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/validator.py): Live credential pings (ATProto, Gemini, OpenAI, Claude, OpenRouter, Telegram, Discord).
   * [`scripts/prereq_check.py`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/prereq_check.py): Dependency validator and host bind-mount state file touch guarantee.
   * [`Dockerfile`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/Dockerfile) & [`docker-compose.yml`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/docker-compose.yml): Production container stack with entrypoint directory collision guard.
   * [`scripts/run_vps.sh`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scripts/run_vps.sh) & [`systemd/omnipost.service`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/systemd/omnipost.service): Headless VPS automation with non-blocking Xvfb lifecycle.

---

## 2. Artifact Lifecycle & Visual Proofing Pipeline

OmniPost generates local visual assets offline without relying on external design APIs.

```
                  Daily Research & Intelligence
                               │
                               ▼
                    scripts/repurpose.py
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   render/infocard.py                    render/carousel.py
  (Pillow 16:9 Generator)              (HTML + Headless CDP)
            │                                     │
            ▼                                     ▼
scratch/infocards/daily_card.png      scratch/carousels/preview.html
            │                                     │
            │                         (Open in browser for visual proof)
            │                                     │
            │                                     ▼
            │                         scratch/carousels/architecture_carousel.pdf
            │                                     │
            ▼                                     ▼
   Attached to X, Bluesky,               Attached to LinkedIn
     and Meta Threads                     via CDP Document Upload
```

### Exact File Locations
* **Daily Schedule Ledger:** [`drafts/YYYY-MM-DD.json`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/drafts/)  
  Contains polymorphic payloads, character counts, due timestamps, and media file paths for each slot.
* **Infographic PNGs:** [`scratch/infocards/daily_card.png`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scratch/infocards/)  
  1200x675 dark-mode PNG image cards featuring headline, takeaway bullets, and author badge.
* **Carousel HTML Previews:** [`scratch/carousels/preview.html`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scratch/carousels/preview.html)  
  High-resolution 1080x1080 standalone HTML document for local visual inspection in any web browser.
* **LinkedIn Vector PDF:** [`scratch/carousels/architecture_carousel.pdf`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/scratch/carousels/architecture_carousel.pdf)  
  5-slide vector PDF document uploaded directly to LinkedIn's document composer.
* **Unified State Ledger:** [`state.json`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/state.json)  
  Crash-safe atomic ledger recording platform publication URLs, timestamps, and error states.

### Visual Proofing CLI
To inspect or generate a standalone carousel manually:
```bash
# Render HTML preview and vector PDF from today's draft:
python -m render.carousel

# Generate HTML preview only:
python -m render.carousel --preview-only
```
Double-click `scratch/carousels/preview.html` to inspect the rendered slides in your browser before they are posted to LinkedIn.

---

## 3. The 5-Slide Carousel Architecture

The revamped carousel design system follows a high-density, authoritative dark-tech aesthetic (`#0B0F19` canvas, `#161F30` cards, `#10B981` Emerald and `#06B6D4` Cyan accents):

1. **Slide 1 — Hero Hook:** High-contrast gradient headline + category badge + author attribution.
2. **Slide 2 — The Architectural Context:** Explains the core problem, coordination bottlenecks, and system constraints.
3. **Slide 3 — Deep Technical Breakdown:** Monospace code block / pattern implementation + engineering insight.
4. **Slide 4 — Implementation Checklist:** Bulleted takeaways and concrete production rules.
5. **Slide 5 — Strategic Outro:** Bottom-line takeaway + branded call-to-action button.

---

## 4. Live Verification Record (All 4 Networks Verified)

> [!IMPORTANT]
> **Live Production Run: Verified & Operational across all 4 networks.**

| Platform | Protocol | Status | Live Evidence |
| :--- | :--- | :---: | :--- |
| **X (Twitter)** | Stealth Browser CDP | **SUCCESS** | Verified live on profile feed.<br>[View Live Tweet](https://x.com/Lordporus/status/2107106701006827729) |
| **Bluesky** | ATProto XRPC | **SUCCESS** | Verified live via ATProto record query.<br>[View Live Post](https://bsky.app/profile/lordporus.bsky.social/post/3mx52tye73a2t) |
| **LinkedIn** | Stealth Browser CDP | **SUCCESS** | Verified live via feed toast & activity URN.<br>[View Live Post](https://www.linkedin.com/feed/update/urn:li:activity:7512874289356771328/) |
| **Meta Threads** | Stealth Browser CDP | **SUCCESS** | Verified live via profile feed check.<br>[View Live Profile](https://www.threads.com/@ig_lordporus) |

---

## 5. Deployment Ecosystem: Dual-Mode Architecture

OmniPost supports two distinct unattended production deployments:

### Option A: Docker Container Stack
* **Orchestration:** `docker compose up -d`
* **Persistent Volumes:**
  * `browser_profile:/app/browser-data`: Preserves logged-in Chromium sessions.
  * `./state.json:/app/state.json`: Synchronizes the atomic ledger to the host.
  * `./drafts:/app/drafts`: Shares daily plans with external tools.
* **Healthcheck:** Automatic health audit via `python scripts/doctor.py --healthcheck` every 5 minutes.
* **Directory Collision Guard:** `scripts/docker-entrypoint.sh` blocks startup if host bind mounts create directories instead of files.

### Option B: Headless Linux VPS (Systemd)
* **1-Click Installer:** `sudo bash scripts/deploy_vps.sh`
* **Non-Blocking Xvfb Lifecycle:** `scripts/run_vps.sh` spawns `Xvfb :99` in the background, verifies socket initialization, and launches `scripts/daemon.py`.
* **Process Persistence:** `systemd/omnipost.service` provides automatic crash restarts (`Restart=always`, `RestartSec=15`).

---

## 6. How to Run OmniPost

### Quick Onboarding:
```powershell
# Interactive 6-step CLI wizard:
python setup.py

# Or completely non-interactive for headless CI:
python setup.py --non-interactive
```

### Manual Trigger Drill:
```powershell
# Run the daily research & plan generation pipeline:
python scripts/pipeline.py

# Verify schedule gatekeeper in dry-run mode:
python scripts/autoposter.py --dry-run
```

### Unattended Daemon:
```powershell
# Background continuous loop:
python scripts/daemon.py
```
