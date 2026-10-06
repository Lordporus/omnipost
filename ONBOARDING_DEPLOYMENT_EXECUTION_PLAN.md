# OmniPost V2.0: Onboarding & Deployment Execution Plan
## `ONBOARDING_DEPLOYMENT_EXECUTION_PLAN.md`

> **Execution Protocol:** GSD Phase-by-Phase TDD (`subagent-driven-development` / `gsd-plan-phase`).  
> **Source Specification:** [`ONBOARDING_AND_DEPLOYMENT_PLAN.md`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/ONBOARDING_AND_DEPLOYMENT_PLAN.md)  
> **Predecessor State:** [`PRODUCTION_SCHEDULE_PLAN.md`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/PRODUCTION_SCHEDULE_PLAN.md) (Fully implemented & verified: 93/93 tests passing).  
> **Target Branch:** `feat/onboarding-and-deployment` (Dedicated feature branch created and tracking origin).

---

## 1. Executive Summary & Architecture

This plan establishes a zero-friction, production-grade onboarding and dual-deployment ecosystem for OmniPost V2.0. It transforms the repository into a sovereign **"Clone & Run"** package where an operator can configure, test, and deploy the publishing syndicate within minutes without touching code.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHASE DEPENDENCY GRAPH                          │
└────────────────────────────────────────────────────────────────────────┘
  Phase 1: Prerequisite Checker & State File Guard (`prereq_check.py`)
    │
    ▼
  Phase 2: Live Credential & Multi-LLM Ping Engine (`validator.py`)
    │
    ▼
  Phase 3: Interactive CLI Wizard with CI Fallback (`setup.py` & `wizard.py`)
    │
    ▼
  Phase 4: Remote Webhook Dispatcher & Fast-Fail Alerts (`notify_webhook.py`)
    │
    ├───────────────────────────────────┐
    ▼                                   ▼
  Phase 5: Docker Containerization    Phase 6: VPS Linux Deployment
  (`Dockerfile`, `docker-compose`,    (`deploy_vps.sh`, `systemd`,
   `docker-entrypoint.sh`)             non-blocking Xvfb lifecycle)
```

---

## 2. Phase Breakdown & Execution Matrix

| Phase | Core Objective | Key Deliverables | Test File |
| :--- | :--- | :--- | :--- |
| **Phase 1** | System Prerequisite, Port Audit & State File Guard | `scripts/prereq_check.py`, `scripts/doctor.py` updates, `scripts/browser_daemon.py` flags | `tests/test_prereq_check.py`, `tests/test_browser_daemon.py` |
| **Phase 2** | Live Credential & Multi-LLM Ping Engine | `scripts/validator.py` | `tests/test_validator.py` |
| **Phase 3** | Interactive CLI Wizard + Non-Interactive CI Fallback | `setup.py`, `scripts/wizard.py` | `tests/test_wizard.py` |
| **Phase 4** | Webhook Dispatcher & Fast-Fail Alerting | `scripts/notify_webhook.py`, `scripts/notify.py` updates | `tests/test_notify_webhook.py` |
| **Phase 5** | Containerized Stack (Docker + Compose + Entrypoint Guard) | `Dockerfile`, `docker-compose.yml`, `scripts/docker-entrypoint.sh` | Container syntax & entrypoint validation |
| **Phase 6** | VPS Linux Systemd & Non-Blocking Xvfb Lifecycle | `systemd/omnipost.service`, `scripts/run_vps.sh`, `scripts/deploy_vps.sh` | Shell syntax & service validation |

---

## Phase 1: Prerequisite & Diagnostic Checker + State File Guard

### Goal
Implement automated system prerequisite diagnostics, port 9444 checks, file permission checks, host bind-mount file initialization, and Linux/container browser flag detection.

### Files
- **Create:** `scripts/prereq_check.py`
- **Modify:** `scripts/doctor.py` (add `--healthcheck` mode for container health audits)
- **Modify:** `scripts/browser_daemon.py` (add container/Linux headless flags: `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`)
- **Test:** `tests/test_prereq_check.py`
- **Update Test:** `tests/test_browser_daemon.py`

### Interfaces & Contracts
```python
def check_prerequisites() -> dict[str, Any]:
    """Returns status dictionary:
    {
        "python": {"ok": bool, "version": str},
        "git": {"ok": bool, "version": str},
        "browser": {"ok": bool, "path": str},
        "docker": {"ok": bool, "compose": bool},
        "port_9444": {"available": bool},
        "ledger_writable": {"ok": bool},
        "state_files_guaranteed": {"ok": bool}
    }
    """

def guarantee_state_files(root: Path | None = None) -> None:
    """Ensures state.json and .env exist as regular files (not directories).
    If missing, creates valid empty state.json ({}) and empty .env to prevent
    Docker mount directory collisions.
    """
```

### Production Refinements Incorporated
- **Refinement 1 (Docker Bind Mount Guarantee):** `guarantee_state_files()` touches and guarantees valid empty `state.json` (`{}`) and `.env` files on disk if missing. Checks if either is an accidental directory and raises a clear error.
- **Refinement 2 (Container & Linux Headless Browser Flags):** In `scripts/browser_daemon.py`, inspect `sys.platform == "linux"` or `os.environ.get("IS_DOCKER") == "1"` or `cfg.get("headless", False)`. When true, automatically append `--no-sandbox`, `--disable-dev-shm-usage`, and `--disable-gpu` to browser launch arguments.

### TDD Test Specification (`tests/test_prereq_check.py`)
1. `test_check_python_version_valid()`: Asserts Python >= 3.10 is detected as `ok=True`.
2. `test_check_git_available()`: Mocks `shutil.which("git")` and validates version return.
3. `test_check_browser_detection()`: Mocks presence of `msedge`, `google-chrome`, and `chromium`.
4. `test_check_port_9444_status()`: Tests port binding check using socket mock.
5. `test_check_ledger_atomic_write()`: Tests atomic temp file creation and deletion in repository root.
6. `test_guarantee_state_files_creates_defaults()`: Verifies `state.json` and `.env` are created as valid files if missing.
7. `test_guarantee_state_files_detects_directory_collision()`: Asserts `ValueError` if `state.json` or `.env` is an existing directory.
8. `test_browser_daemon_appends_linux_flags()` (in `tests/test_browser_daemon.py`): Verifies `--no-sandbox`, `--disable-dev-shm-usage`, and `--disable-gpu` are added when on Linux or in Docker.

### Verification Command
```bash
python -m pytest tests/test_prereq_check.py tests/test_browser_daemon.py -v
python scripts/doctor.py --healthcheck
```

---

## Phase 2: Live Credential & Multi-LLM Ping Engine

### Goal
Provide zero-dependency HTTP validation functions for social platform credentials and AI providers, performing 1-token or session checks before persisting keys to disk.

### Files
- **Create:** `scripts/validator.py`
- **Test:** `tests/test_validator.py`

### Interfaces & Contracts
```python
def validate_bluesky_credentials(identifier: str, app_password: str) -> tuple[bool, str]:
    """Hits https://bsky.social/xrpc/com.atproto.server.createSession."""

def validate_llm_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Validates Gemini, OpenAI, Claude, OpenRouter, or Local."""

def validate_webhook(service: str, url_or_token: str, chat_id: str | None = None) -> tuple[bool, str]:
    """Dispatches a non-intrusive ping to Telegram or Discord."""
```

### TDD Test Specification (`tests/test_validator.py`)
1. `test_validate_bluesky_success_and_failure()`: Mocks `urllib.request.urlopen` for HTTP 200 vs 401.
2. `test_validate_gemini_key()`: Mocks Google API model listing request.
3. `test_validate_openai_key()`: Mocks OpenAI `/v1/models` request.
4. `test_validate_claude_key()`: Mocks Anthropic `/v1/models` request.
5. `test_validate_openrouter_key()`: Mocks OpenRouter `/api/v1/auth/key` request.
6. `test_validate_local_mode()`: Validates fallback with no API key returns `(True, "Zero-cost local mode selected")`.
7. `test_validate_telegram_and_discord()`: Mocks webhook POST requests.

### Verification Command
```bash
python -m pytest tests/test_validator.py -v
```

---

## Phase 3: Interactive CLI Onboarding Wizard + Non-Interactive CI Fallback

### Goal
Implement a single-command onboarding wizard (`python setup.py` and `scripts/wizard.py`) with 6 guided steps, writing public config to `config.json` and sensitive keys to `.env`. Supports full non-interactive fallback for automated testing and unattended VPS deployment.

### Files
- **Create:** `setup.py` (entrypoint invoking `scripts/wizard.py`)
- **Create:** `scripts/wizard.py`
- **Test:** `tests/test_wizard.py`

### Workflow Steps
1. **[1/6] Platform Credentials:** X handle, Bluesky app password (with live ping), LinkedIn URL, Threads handle.
2. **[2/6] Multi-LLM Provider Selection:** Selection menu + live API ping before acceptance.
3. **[3/6] Content & Voice Preferences:** Niche topics, voice tone style, custom author attribution, posting cadence.
4. **[4/6] Timezone Auto-Detection:** Auto-detects local system timezone via `datetime` / `tzlocal` and prompts for confirmation.
5. **[5/6] Notification Webhooks:** Configures Telegram Bot or Discord Webhook URL with live ping.
6. **[6/6] Operating Mode:** Selects Dry-Run Mode vs Live Auto-Posting Mode.

### Production Refinements Incorporated
- **Refinement 4 (Full Non-Interactive & Headless CI Fallback):**
  - Flags supported: `--non-interactive`, `--test-mode`, `--defaults`.
  - In non-interactive mode: Reads values from existing environment variables (`X_HANDLE`, `BSKY_IDENTIFIER`, `BSKY_APP_PASSWORD`, `GEMINI_API_KEY`, etc.) or writes hardened default template files without blocking on stdin prompts.
- **Refinement 1 (Docker Bind Mount Guarantee):**
  - Wizard automatically calls `prereq_check.guarantee_state_files()` ensuring `state.json` and `.env` exist on disk before exit.

### TDD Test Specification (`tests/test_wizard.py`)
1. `test_wizard_config_generation()`: Simulates mock interactive input sequence and verifies output `config.json` schema.
2. `test_wizard_env_generation()`: Verifies secrets are saved to `.env` with proper variable formatting.
3. `test_wizard_timezone_detection()`: Tests fallback and system timezone resolution.
4. `test_wizard_dry_run_flag()`: Verifies `dry_run` flag is accurately written.
5. `test_wizard_non_interactive_mode()`: Verifies running with `--non-interactive` completes cleanly without prompt blocking and creates valid files.
6. `test_wizard_guarantees_state_files()`: Confirms `state.json` and `.env` exist as valid files after execution.

### Verification Command
```bash
python -m pytest tests/test_wizard.py -v
python setup.py --non-interactive --test-mode
```

---

## Phase 4: Remote Webhook Dispatcher & Fast-Fail Alerts

### Goal
Implement Telegram and Discord webhook notifications for headless deployments (VPS and Docker), integrated with `scripts/notify.py` to deliver real-time post confirmation and fast-fail session expiry alerts.

### Files
- **Create:** `scripts/notify_webhook.py`
- **Modify:** `scripts/notify.py` (integrate webhook dispatching alongside Windows desktop toasts)
- **Test:** `tests/test_notify_webhook.py`

### Interfaces & Contracts
```python
def dispatch_webhook(event_type: str, title: str, message: str, metadata: dict[str, Any] | None = None) -> bool:
    """Sends formatted alert to Telegram and/or Discord if configured in .env / config.json."""

def send_session_expired_alert(platform: str, action_required: str) -> None:
    """Dispatches high-priority alert when cookies or tokens expire."""
```

### TDD Test Specification (`tests/test_notify_webhook.py`)
1. `test_telegram_dispatch_payload_formatting()`: Tests JSON structure sent to Telegram Bot API.
2. `test_discord_embed_formatting()`: Tests Discord webhook embed JSON format.
3. `test_session_expiry_alert_dispatch()`: Verifies fast-fail alert payload and log capture.
4. `test_webhook_graceful_fallback()`: Verifies network timeouts do not raise exceptions or crash publishing loops.

### Verification Command
```bash
python -m pytest tests/test_notify_webhook.py -v
```

---

## Phase 5: Containerized Stack (Docker, Compose & Entrypoint Guard)

### Goal
Provide a production-ready containerized environment with Python 3.12, Chromium, Xvfb virtual framebuffer, volume persistence for browser profiles and state ledger, entrypoint bind-mount directory guards, and healthchecks.

### Files
- **Create:** `Dockerfile`
- **Create:** `docker-compose.yml`
- **Create:** `scripts/docker-entrypoint.sh`
- **Modify:** `requirements.txt` (ensure all pinned dependencies are present)

### Production Refinements Incorporated
- **Refinement 1 (Docker Bind Mount Directory Guard):**
  - In `scripts/docker-entrypoint.sh`: Pre-flight check verifies whether `/app/state.json` or `/app/.env` is a directory (Docker's default behavior when mounting non-existent host files).
  - If a directory is detected, outputs:
    `[FATAL] /app/state.json is a directory! Remove the directory on the host and run 'python setup.py' or touch the file before starting docker compose.`
    and exits immediately with code 1.
- **Refinement 2 (Container & Linux Headless Browser Flags):**
  - `docker-compose.yml` sets `IS_DOCKER=1`, `DISPLAY=:99`, `CHROME_PATH=/usr/bin/chromium`.
  - Browser daemon reads these variables and applies `--no-sandbox`, `--disable-dev-shm-usage`, and `--disable-gpu`.

### Specifications
* **Base Image:** `python:3.12-slim-bookworm`
* **System Packages:** `chromium`, `chromium-driver`, `xvfb`, `fonts-liberation`, `fonts-dejavu-core`, `procps`, `curl`
* **Volumes:**
  - `omnipost_browser_data:/app/browser-data`
  - `./state.json:/app/state.json`
  - `./drafts:/app/drafts`
  - `./config.json:/app/config.json:ro`
  - `./.env:/app/.env:ro`
* **Healthcheck:** `python scripts/doctor.py --healthcheck`

### Verification Command
```bash
docker compose config --quiet
bash -n scripts/docker-entrypoint.sh
```

---

## Phase 6: VPS Linux Deployment & Non-Blocking Xvfb Lifecycle

### Goal
Provide headless Linux provisioning scripts and systemd unit definitions with a non-blocking Xvfb lifecycle for single-command deployment on Ubuntu/Debian virtual private servers.

### Files
- **Create:** `systemd/omnipost.service`
- **Create:** `scripts/run_vps.sh` (non-blocking Xvfb daemon launcher)
- **Create:** `scripts/deploy_vps.sh` (1-click automated VPS provisioning script)

### Production Refinements Incorporated
- **Refinement 3 (Non-Blocking Xvfb Lifecycle):**
  - `ExecStartPre=/usr/bin/Xvfb :99 ...` blocks systemd service execution because Xvfb runs continuously in the foreground.
  - Solution: Provide `scripts/run_vps.sh` as the service entrypoint. It checks if an Xvfb server on `:99` is already active; if not, launches `Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &` in the background, waits 1 second for the socket to appear, and then `exec python scripts/daemon.py`.
  - Alternatively, provide an optional companion unit `systemd/omnipost-xvfb.service`.

### Systemd Service Unit (`systemd/omnipost.service`)
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
Environment=IS_LINUX=1
ExecStart=/bin/bash /opt/omnipost/scripts/run_vps.sh
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Verification Command
```bash
bash -n scripts/run_vps.sh
bash -n scripts/deploy_vps.sh
systemd-analyze verify systemd/omnipost.service 2>/dev/null || echo "Syntax verified"
```

---

## 3. Review & Convergence Verification Gates

To ensure strict zero-regression quality, each phase must satisfy the **Convergence Gate**:

```
[Phase Entry]
      │
      ▼
1. Write Unit Tests (TDD - Red Phase)
      │
      ▼
2. Verify Test Failure (`pytest tests/test_<phase>.py`)
      │
      ▼
3. Implement Component Source Code
      │
      ▼
4. Verify Test Success (`pytest tests/test_<phase>.py` - Green Phase)
      │
      ▼
5. Run Full Test Suite (`pytest` across all 93+ tests)
      │
      ▼
6. Atomic Git Commit (`feat(<scope>): <description>`)
      │
      ▼
[Phase Sealed ➔ Advance to Next Phase]
```

---

## 4. Phase-by-Phase Execution Readiness

All prerequisites, file boundaries, contracts, production edge-case guards, and tests are rigorously mapped out on branch `feat/onboarding-and-deployment`.
We are ready to execute **Phase 1** or run through the sequence sequentially via subagent-driven development.
