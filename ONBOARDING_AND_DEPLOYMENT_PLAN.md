# OmniPost V2.0: Onboarding & Dual Deployment Specification (`ONBOARDING_AND_DEPLOYMENT_PLAN.md`)

**Document Date:** October 2026  
**Audience:** Operators, DevOps Engineers, and System Architects  
**Scope:** Zero-Friction Setup, Interactive CLI Onboarding, Credential Validation & Dual-Mode Deployment (Docker + Headless Linux VPS)  
**Complementary Document:** [`PRODUCTION_SCHEDULE_PLAN.md`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/PRODUCTION_SCHEDULE_PLAN.md) (remains untouched)

---

## 1. Architecture & "Git Clone & Run" Philosophy

### 1.1 The Core Philosophy
OmniPost is designed as a self-contained, sovereign marketing syndicate. Any user or engineer should be able to clone the repository, execute a single bootstrap command, and have an autonomous, multi-platform publishing agent running in minutes—with zero manual edits to source code files.

```
                           ┌────────────────────────────┐
                           │      git clone <repo>      │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │      python setup.py       │
                           │   (Interactive Wizard)     │
                           └─────────────┬──────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │    Deployment Option A    │                   │    Deployment Option B    │
   │    Local / Docker Stack   │                   │    Headless Linux VPS     │
   │   `docker compose up -d`  │                   │      Systemd Service      │
   └───────────────────────────┘                   └───────────────────────────┘
```

### 1.2 Minimal Prerequisites & Automated Pre-flight Checker
Before initiating configuration, the onboarding harness runs an automated prerequisite diagnostic (`scripts/prereq_check.py` or inline in `setup.py`):

| Dependency | Minimum Floor | Purpose | Auto-Verification Method |
| :--- | :--- | :--- | :--- |
| **Python** | `>= 3.10` (Target: `3.12`) | Core runner, adapters, rendering | `sys.version_info >= (3, 10)` |
| **Chromium / Edge** | Chrome/Edge/Chromium | CDP browser automation for X, LinkedIn, Threads | Binary path detection in `PATH` / default OS dirs |
| **Git** | `>= 2.30` | Version tracking, update syncing | `git --version` check |
| **Docker & Compose** | Docker v24+, Compose v2+ | Optional containerized deployment | `docker compose version` check |

#### Prerequisite Diagnostic Code Contract (`scripts/prereq_check.py`)
```python
import shutil
import sys


def check_prerequisites() -> dict[str, bool]:
    results = {
        "python": sys.version_info >= (3, 10),
        "git": shutil.which("git") is not None,
        "browser": False,
    }
    # Check for Edge, Chrome, or Chromium
    browser_binaries = ["msedge", "google-chrome", "chromium-browser", "chromium"]
    for b in browser_binaries:
        if shutil.which(b):
            results["browser"] = True
            break
    return results
```

---

## 2. Interactive CLI Onboarding Wizard (`setup.py`)

The interactive onboarding wizard is a zero-dependency CLI application (`python setup.py`) that steps the operator through configuration, validates credentials on the fly, tests live connectivity, and outputs a hardened `.env` and `config.json`.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   OMNIPOST V2.0 INTERACTIVE ONBOARDING                 │
├────────────────────────────────────────────────────────────────────────┤
│  [1/6] Platform Credential & Account Setup (X, Bsky, LI, Threads)     │
│  [2/6] Multi-LLM Provider Selection & Live Ping Check                  │
│  [3/6] Content Tone, Niches & Repurposing Preferences                  │
│  [4/6] Timezone Auto-Detection & Schedule Window Calibration           │
│  [5/6] Headless Notification Webhooks (Telegram / Discord)             │
│  [6/6] Execution Mode Selection (Dry-Run vs Live Autonomous Mode)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Platform Credentials Setup
The wizard checks which channels the operator desires to activate and writes sensitive keys to `.env` while preserving public identifiers in `config.json`.

1. **X (Twitter):**
   * Prompt: *Enable X automation? [Y/n]*
   * Prompt: *X Handle (e.g., Lordporus):*
   * Mode: Uses local browser session profile.
2. **Bluesky:**
   * Prompt: *Enable Bluesky syndication? [Y/n]*
   * Prompt: *Bluesky Handle (e.g., handle.bsky.social):*
   * Prompt: *App Password (hidden input):*
   * **Live Validation:** Wizard executes an immediate HTTP call to `https://bsky.social/xrpc/com.atproto.server.createSession`. If rejected, it immediately re-prompts the operator without saving bad credentials.
3. **LinkedIn:**
   * Prompt: *Enable LinkedIn syndication? [Y/n]*
   * Prompt: *LinkedIn Profile URL (e.g., https://linkedin.com/in/username):*
   * Prompt: *Minimum gap between posts (hours) [default: 4]:*
4. **Meta Threads:**
   * Prompt: *Enable Threads syndication? [Y/n]*
   * Prompt: *Threads Handle (e.g., @username):*

---

### Step 2: Multi-LLM Provider Selection with Live Ping Verification
OmniPost supports multiple AI providers for synthesizing daily topics and polymorphic repurposing. The wizard allows selecting a primary provider (plus optional fallback) and **pings the API immediately** with a single-token test to guarantee the key is active before continuing.

Supported Providers:
* **Google Gemini** (`gemini-2.0-flash` or `gemini-1.5-pro` via `GEMINI_API_KEY`)
* **OpenAI** (`gpt-4o` or `gpt-4o-mini` via `OPENAI_API_KEY`)
* **Anthropic Claude** (`claude-3-5-sonnet` via `ANTHROPIC_API_KEY`)
* **OpenRouter** (Aggregator for DeepSeek, Llama 3, Claude via `OPENROUTER_API_KEY`)
* **Local / Rule-based Heuristic** (Zero-cost, no API key required)

#### Live LLM Validation Matrix
```python
def validate_llm_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Validates an API key with a minimal 1-token query before persisting."""
    try:
        if provider == "gemini":
            import urllib.request, json
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=8) as resp:
                return (resp.status == 200, "Gemini API key active")
        elif provider == "openai":
            import urllib.request, json
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return (resp.status == 200, "OpenAI API key active")
        elif provider == "claude":
            import urllib.request, json
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return (resp.status == 200, "Claude API key active")
        elif provider == "openrouter":
            import urllib.request, json
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return (resp.status == 200, "OpenRouter API key active")
    except Exception as exc:
        return (False, f"Validation failed: {exc}")
    return (True, "Zero-cost local mode selected")
```

---

### Step 3: Posting Preferences & Voice Configuration
The wizard configures editorial boundaries in `config.json` and updates `references/voice-profile.local.md`:
* **Target Niches / Subreddits:** Operator enters comma-separated topics (e.g. `LocalLLaMA, artificial, AI agents, solopreneur`).
* **Tone & Framing:** Selection between:
  1. *Hard-hitting Contrarian Technical* (Senior Architect / Builder voice)
  2. *Educational & Framework-Driven* (Cheat sheets, visual breakdowns)
  3. *Conversational Founder / Indie Hacker* (Journey updates, daily experiments)
* **Custom Signatures & Brand Attributions:** (e.g. `author: "@Lordporus • OmniPost"`).
* **Posting Frequency & Slots:**
  * Standard 4-Slot Cadence (`["13:00", "16:00", "20:00", "00:00"]`) with 45-minute jitter.
  * Custom time slots if specified by operator.

---

### Step 4: System & Timezone Auto-Detection
To avoid schedule drift between UTC servers and the operator's audience:
1. Auto-detects system timezone using `tzlocal` / `datetime.now().astimezone().tzname()`.
2. Asks for user confirmation:
   ```
   [?] Detected system timezone as: Asia/Kolkata (IST, UTC+05:30)
       Use this timezone for scheduled post jitter? [Y/n]
   ```
3. Sets `"timezone": "Asia/Kolkata"` or `"local"` in `config.json`.

---

### Step 5: Notification Webhook Integration
For headless deployments (VPS and Docker) where desktop notifications cannot be seen, the wizard enables instant webhook alerts:
* **Option A: Telegram Bot:**
  * Prompts for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
  * Sends an immediate test ping message (*"OmniPost Onboarding: Webhook test successful."*).
* **Option B: Discord Webhook:**
  * Prompts for `DISCORD_WEBHOOK_URL`.
  * Sends an immediate test embed.
* **Option C: Console / Local Log Only:**
  * Suppresses external webhooks.

---

### Step 6: Mode Selection (Dry-Run vs Live)
Before exiting, the wizard asks:
```
[?] Select initial operating mode:
  > 1. Dry-Run Mode (generates plans, renders cards, validates DOM without posting)
    2. Live Autonomous Mode (posts live to connected networks when slots trigger)
```
Writes `"dry_run": true/false` into `config.json`.

---

## 3. Dual Deployment Configurations

OmniPost provides two production-grade deployment patterns:
1. **Containerized Stack (Docker Compose)** for isolated environments.
2. **Headless Linux VPS (Systemd)** for bare-metal or cloud VMs ($5/mo Hetzner/DigitalOcean).

---

### Deployment Option A: Docker Containerized Deployment

#### 3.1 Architecture Overview
A single Docker image containing Python 3.12, Chromium, Xvfb (virtual framebuffer for stealth browser sessions), and font packages (for rendering Pillow infocards and PDF carousels).

```
┌─────────────────────────────────────────────────────────────┐
│                       Docker Host                           │
│                                                             │
│  ┌───────────────────────┐         ┌─────────────────────┐  │
│  │ Named Volume:         │ ◄─────► │ /app/browser-data   │  │
│  │ omnipost_browser_data │         │ (Chromium Profile)  │  │
│  └───────────────────────┘         └─────────────────────┘  │
│                                                             │
│  ┌───────────────────────┐         ┌─────────────────────┐  │
│  │ Bind Mount:           │ ◄─────► │ /app/state.json     │  │
│  │ ./state.json          │         │ (Crash-safe Ledger) │  │
│  └───────────────────────┘         └─────────────────────┘  │
│                                                             │
│  ┌───────────────────────┐         ┌─────────────────────┐  │
│  │ Bind Mount:           │ ◄─────► │ /app/drafts         │  │
│  │ ./drafts/             │         │ (Polymorphic Plans) │  │
│  └───────────────────────┘         └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2 Production `Dockerfile`
```dockerfile
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

# Install Chromium, Xvfb, fonts, and automation utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    xvfb \
    fonts-liberation \
    fonts-dejavu-core \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Entrypoint script starts Xvfb and launches supervisor/daemon
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "scripts/daemon.py"]
```

#### 3.3 Container Entrypoint (`scripts/docker-entrypoint.sh`)
```bash
#!/usr/bin/env bash
set -e

# Start virtual display buffer
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 1

# Execute passed command (default: python scripts/daemon.py)
exec "$@"
```

#### 3.4 Production `docker-compose.yml`
```yaml
services:
  omnipost:
    build: .
    container_name: omnipost-engine
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - browser_profile:/app/browser-data
      - ./config.json:/app/config.json:ro
      - ./state.json:/app/state.json
      - ./drafts:/app/drafts
      - ./swipe:/app/swipe
      - ./scratch:/app/scratch
    healthcheck:
      test: ["CMD", "python", "scripts/doctor.py", "--healthcheck"]
      interval: 5m
      timeout: 30s
      retries: 3
      start_period: 20s
    environment:
      - DISPLAY=:99
      - BROWSER_PROFILE=/app/browser-data
      - CHROME_PATH=/usr/bin/chromium

volumes:
  browser_profile:
    name: omnipost_browser_data
```

---

### Deployment Option B: VPS Headless Linux Deployment

For operators deploying directly on a headless Ubuntu/Debian VPS without Docker overhead.

#### 3.5 Automated VPS Provisioning Script (`scripts/deploy_vps.sh`)
```bash
#!/usr/bin/env bash
# OmniPost VPS Headless Installer for Ubuntu 22.04 / 24.04 LTS
set -euo pipefail

echo "==> Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

echo "==> Installing Python 3.12, Chromium, Xvfb and fonts..."
sudo apt-get install -y python3 python3-pip python3-venv chromium-browser xvfb \
    fonts-liberation fonts-noto-color-emoji curl git

echo "==> Setting up application directory..."
APP_DIR="/opt/omnipost"
if [ ! -d "$APP_DIR" ]; then
    sudo git clone https://github.com/Lordporus/omnipost.git "$APP_DIR"
fi
sudo chown -R "$USER":"$USER" "$APP_DIR"
cd "$APP_DIR"

echo "==> Initializing Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Running Interactive Onboarding Setup..."
python setup.py

echo "==> Registering Systemd Services..."
sudo cp systemd/omnipost.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable omnipost.service
sudo systemctl start omnipost.service

echo "==> Deployment Complete! Check status with: sudo systemctl status omnipost"
```

#### 3.6 Systemd Service Unit (`systemd/omnipost.service`)
```ini
[Unit]
Description=OmniPost Autonomous Multi-Platform Syndicate
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/omnipost
EnvironmentFile=/opt/omnipost/.env
Environment=DISPLAY=:99
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp
ExecStart=/opt/omnipost/.venv/bin/python /opt/omnipost/scripts/daemon.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

---

## 4. Validation & Pre-Flight Checklist

Before the scheduler starts processing slots, the pre-flight audit routine (`scripts/doctor.py --live`) validates three structural gates. If any gate fails, the system executes **fail-fast error messaging** and dispatches a webhook alert before halting.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          PRE-FLIGHT AUDIT GATES                        │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 1: Network & CDP Port Availability (Port 9444)                    │
│   • Verifies local WebSocket /json/version endpoint responds           │
│   • Confirms HTTP connectivity to target APIs (ATProto, X, LI, etc.)   │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 2: File System & State Ledger Permissions                         │
│   • Confirms write/read access to state.json and drafts/ directory     │
│   • Validates crash-safe atomic rename (temp file -> state.json)       │
├────────────────────────────────────────────────────────────────────────┤
│ GATE 3: Session Expiry & Fast-Fail Alerting                            │
│   • Checks if browser cookies for LinkedIn/Threads/X have expired      │
│   • Tests Bluesky App Password against ATProto session endpoint        │
│   • Triggers instant notification if operator re-login is required     │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Gate 1: Network & CDP Port Availability
* **Diagnostic Check:** Connects to `http://127.0.0.1:9444/json/version` with a 3.0s timeout.
* **Failure Handling:** If unreachable, invokes `scripts/browser_daemon.py` to auto-heal. If port is bound by a foreign process, logs `[FATAL] Port 9444 occupied by foreign PID` and exits with code `2`.

### 4.2 Gate 2: Ledger File Permission Check
* **Diagnostic Check:** Performs an atomic test write:
  ```python
  test_file = ROOT / ".write_test.tmp"
  test_file.write_text("ok", encoding="utf-8")
  test_file.replace(ROOT / ".write_test.verified")
  (ROOT / ".write_test.verified").unlink()
  ```
* **Failure Handling:** Exits immediately with `[FATAL] Read-only filesystem or insufficient permissions on state.json directory`.

### 4.3 Gate 3: Session Expiry & Fast-Fail Alerts
When unattended background workers execute, session timeouts must not stall silently:
1. **Detection:**
   * **LinkedIn:** Redirect to `/login` or `/checkpoint` triggers `session_expired` flag.
   * **Threads:** Presence of `"Log in to continue"` modal triggers `session_expired` flag.
   * **Bluesky:** XRPC `AuthenticationRequired` or `InvalidToken` HTTP 401 response.
2. **Alert Action:**
   * Immediately records the failure in `state.json` ledger.
   * Dispatches high-priority webhook notification to Telegram/Discord:
     ```
     🚨 [OmniPost Alert] Session Expired for Platform: LINKEDIN
     Timestamp: 2026-10-06 14:02 UTC
     Action Required: Operator re-login required in Edge automation profile.
     Automation for LinkedIn is paused. Other platforms will continue operating.
     ```
   * Continues publishing to remaining unaffected networks (zero cascade failures).

---

## 5. File Manifest & Implementation Deliverables

To implement this onboarding and deployment specification without modifying existing core logic, the following new files are to be created:

```
├── setup.py                        # Interactive CLI onboarding wizard
├── requirements.txt                # Pinned production dependencies
├── Dockerfile                      # Production container image with Chromium + Xvfb
├── docker-compose.yml              # Container orchestration stack with volume mounts
├── systemd/
│   └── omnipost.service            # Linux systemd unit file for headless VPS
└── scripts/
    ├── prereq_check.py             # System & binary prerequisite detector
    ├── docker-entrypoint.sh        # Xvfb buffer initialization script
    ├── deploy_vps.sh               # 1-click VPS Ubuntu provisioning script
    └── notify_webhook.py           # Telegram & Discord webhook dispatcher
```

---

## 6. Summary of Architectural Guarantees

1. **Zero UI Bloat:** No resource-heavy web dashboards, Electron wrappers, or CRM baggage. Pure, clean, deterministic CLI and daemon execution.
2. **Privacy First:** All browser sessions, passwords, and tokens remain strictly on your local disk or private VPS.
3. **Partial Failure Isolation:** Session expiry on one network never prevents posts from landing on the other three networks.
4. **Self-Healing:** Crashed browser sessions, machine reboots, and network drops are detected and auto-healed automatically.
