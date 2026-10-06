# OmniPost V2.0

**Autonomous Cross-Platform Publishing Syndicate for AI Agents (X, Bluesky, LinkedIn, Threads) with Zero-Friction Onboarding and Zero API Costs.**

OmniPost V2.0 transforms content distribution from a manual, single-platform chore into a sovereign, unattended publishing syndicate. It aggregates daily technical intelligence, synthesizes polymorphic posts aligned with your personal voice, renders high-resolution visual cards and vector PDF document carousels offline, publishes across four major social networks simultaneously, and cryptographically/visually verifies live publications back into an atomic ledger.

```
       ┌──────────┐   ┌────────────┐   ┌─────────────┐   ┌────────────────────────┐   ┌──────────────┐
 11:00 │ RESEARCH │ → │ REPURPOSE  │ → │ SCHEDULER   │ → │ AUTONOMOUS DISPATCH    │ → │ VERIFY & LOG │
       └──────────┘   └────────────┘   └─────────────┘   └────────────────────────┘   └──────────────┘
        HN, RSS,       1 insight →      Jitter Gate       • X (CDP Stealth)            Read timeline
        ArXiv, Feeds   4 channels +     Wakes only        • Bluesky (ATProto XRPC)     activity URNs
        ~150 stories   PDF carousel     when due          • LinkedIn (ProseMirror/PDF) Store in atomic
                                                          • Threads (Direct DOM upload) state ledger
```

---

## What Makes OmniPost V2.0 Sovereign

* **Zero Cloud API Subscriptions:** Bypasses costly \$200+/month developer tiers on X, LinkedIn, and Threads by automating local, authenticated browser sessions over Chrome DevTools Protocol (CDP).
* **Zero-Browser Bluesky Syndication:** Communicates directly with the ATProto XRPC protocol, parsing rich UTF-8 byte slice facets for mentions and links in microseconds.
* **Polymorphic Repurposing:** Automatically adapts 1 core technical insight into 4 distinct formats:
  * **X (Twitter):** 280-character contrarian hook + bullet points + 16:9 infographic card.
  * **Bluesky:** 300-character technical breakdown with rich facets.
  * **LinkedIn:** 1,500-character case study breakdown + 5-slide 1080x1080 vector PDF carousel.
  * **Meta Threads:** 500-character conversational builder narrative.
* **Offline Vector & Infographic Rendering:** Programmatic Pillow cards (1200x675) and headless CDP PDF carousels (1080x1080) rendered locally with zero external image APIs or heavy C-libraries.
* **Atomic State Ledger with Partial-Failure Isolation:** If one platform encounters a cooldown (e.g. LinkedIn 4-hour gap), successful posts are marked immediately in `state.json` and only pending networks are retried on subsequent ticks. Zero duplicate posts.
* **Dual-Mode Headless Deployment:** Runs locally on Windows with native desktop toast notifications, in Docker with healthchecks and persistent named volumes, or on a \$5/mo Linux VPS with systemd and non-blocking Xvfb.

---

## Feature Comparison Matrix

| Capability | OmniPost V1 (Legacy) | OmniPost V2.0 |
| :--- | :---: | :---: |
| **Supported Networks** | X (Twitter) only | **X, Bluesky, LinkedIn, Threads** |
| **Publishing Protocol** | CDP Browser only | **Stealth CDP + Native ATProto XRPC** |
| **Visual Media Generation** | Basic PNG infocards | **Pillow 16:9 Cards + 5-Slide Vector PDF Carousels** |
| **Content Adaptation** | Monolithic single text | **Polymorphic Per-Channel Engine** |
| **State Tracking** | Flat single-post JSON | **Atomic Schema V2 with Partial-Failure Retries** |
| **Onboarding Experience** | Manual JSON editing | **Interactive 6-Step CLI Wizard (`setup.py`)** |
| **AI Provider Support** | Single provider | **Gemini, OpenAI, Claude, OpenRouter, Local Heuristic** |
| **Deployment Modes** | Local manual script | **Windows Scheduler, Docker Compose & Linux VPS (Systemd)** |
| **Alerting & Monitoring** | Console output | **Windows Desktop Toasts, Telegram & Discord Webhooks** |

---

## Quickstart Guide

### Option 1: Local Interactive Onboarding (Windows / macOS / Linux)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Lordporus/omnipost.git
   cd omnipost
   ```

2. **Run the interactive onboarding wizard:**
   ```bash
   python setup.py
   ```
   * Step 1: Account credentials (X, Bluesky app password, LinkedIn, Threads).
   * Step 2: Multi-LLM provider selection with immediate 1-token live ping validation.
   * Step 3: Niche topics, voice tone style, custom author attribution, and time slots.
   * Step 4: System timezone auto-detection.
   * Step 5: Telegram or Discord webhook alerts.
   * Step 6: Initial operating mode (Dry-Run vs Live Autonomous Mode).

3. **Verify system health:**
   ```bash
   python scripts/prereq_check.py
   python scripts/doctor.py --healthcheck
   ```

4. **Run the autonomous background daemon:**
   ```bash
   python scripts/daemon.py
   ```

---

### Option 2: Docker Containerized Stack

OmniPost provides a production container image packaged with Chromium, Xvfb virtual framebuffer, and font rendering.

1. **Configure environment:**
   ```bash
   # Run onboarding in non-interactive mode or copy templates:
   python setup.py --non-interactive
   ```

2. **Launch container stack:**
   ```bash
   docker compose up -d
   ```

3. **Inspect logs & health status:**
   ```bash
   docker compose logs -f
   docker compose ps
   ```
* *Persistent Storage:* Browser sessions are preserved in the `omnipost_browser_data` Docker volume. `state.json` and `drafts/` are synchronized to your host directory.

---

### Option 3: 1-Click Headless Linux VPS Deployment (Ubuntu 22.04 / 24.04)

Deploy onto a bare-metal server or cloud VPS (Hetzner, DigitalOcean, Linode):

```bash
sudo bash scripts/deploy_vps.sh
```

This single command:
1. Installs system dependencies (`chromium`, `xvfb`, fonts, `python3-venv`).
2. Configures the isolated application directory at `/opt/omnipost`.
3. Runs the onboarding configuration wizard.
4. Registers and starts the non-blocking systemd background service `omnipost.service`.

Check status anytime:
```bash
sudo systemctl status omnipost
sudo journalctl -u omnipost -f
```

---

## Visual Carousel & Artifact Pipeline

OmniPost automatically produces high-authority visual assets for daily posts:

```bash
# Render HTML preview and 1080x1080 vector PDF carousel from today's draft:
python -m render.carousel

# Generate HTML preview only:
python -m render.carousel --preview-only
```

* **HTML Visual Proofing:** Open `scratch/carousels/preview.html` in any web browser to proof slides locally before they publish.
* **LinkedIn Vector PDF:** Located at `scratch/carousels/architecture_carousel.pdf` and automatically attached during LinkedIn post dispatch.
* **16:9 Infocards:** Located at `scratch/infocards/daily_card.png` and attached to X, Bluesky, and Threads.

---

## CLI & Developer Tool Reference

| Command | Purpose |
| :--- | :--- |
| `python setup.py` | Interactive 6-step CLI onboarding wizard. |
| `python setup.py --non-interactive` | Unattended onboarding reading defaults from environment variables. |
| `python scripts/prereq_check.py` | Validates Python, Git, Browser, Docker, Port 9444, and ledger permissions. |
| `python scripts/doctor.py --live` | Comprehensive audit testing network feeds, browser CDP, and platform sessions. |
| `python scripts/doctor.py --healthcheck` | Fast binary check (exit code 0/1) for Docker/container monitoring. |
| `python scripts/pipeline.py` | Runs research, generates polymorphic drafts, and populates `drafts/YYYY-MM-DD.json`. |
| `python scripts/autoposter.py --dry-run` | Evaluates schedule slots and simulates dispatch without live posting. |
| `python scripts/publish_now.py --text "..."` | On-demand instant broadcast across any combination of platforms. |
| `python -m render.carousel` | Generates 1080x1080 HTML preview and vector PDF carousel. |
| `python scripts/daemon.py` | Continuous background supervisor managing morning research and scheduled posting. |

---

## Architectural Guarantees & Safety Boundaries

1. **Zero Cascade Failures:** An authentication challenge or network hiccup on LinkedIn will never prevent your posts from landing on X, Bluesky, or Threads.
2. **Crash-Safe Atomic Ledger:** Every write to `state.json` uses temporary atomic replacement (`replace_file_content` / atomic rename), preventing corrupted states during sudden power loss or reboots.
3. **Browser Auto-Healer:** If Edge or Chromium crashes, `scripts/browser_daemon.py` detects the closed port 9444 and automatically respawns the browser with appropriate sandbox and display flags.
4. **Data Sovereignty:** All cookies, session tokens, drafts, and encryption keys remain strictly on your local disk or private VPS. No 3rd-party SaaS databases.

---

## License

MIT License. See [LICENSE](LICENSE) for full details.
