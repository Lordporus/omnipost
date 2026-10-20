# Technology Stack

**Analysis Date:** 2026-10-20

## Languages

**Primary:**
- Python 3.10+ (3.12 in containers) - Entire application: `scripts/`, `adapters/`, `render/`, `tests/`, `setup.py`

**Secondary:**
- Bash - Linux/macOS provisioning and process startup: `setup.sh`, `scripts/run_vps.sh`, `scripts/deploy_vps.sh`, `scripts/docker-entrypoint.sh`
- Windows Batch - Local bootstrap and browser launch: `setup.bat`, `launch_edge.bat`
- PowerShell - Windows toast notifications (`scripts/notify.py`) and Task Scheduler registration (`scripts/setup_scheduler.ps1`)
- JavaScript (embedded strings) - DOM inspection/injection executed over CDP in `adapters/x.py`, `adapters/linkedin.py`, `adapters/threads.py`, `scripts/post.py`, `scripts/research.py`, `scripts/analytics.py`
- HTML/CSS - Visual templates rendered to PNG/PDF: `render/template.html`, `render/card_template.html`
- JSON/YAML - Runtime configuration, drafts, ledger, CI and Compose definitions: `config.example.json`, `state.json`, `drafts/*.json`, `.github/workflows/ci.yml`, `docker-compose.yml`

## Runtime

**Environment:**
- CPython. Minimum enforced at 3.10 by `scripts/doctor.py` and `scripts/prereq_check.py`; container uses `python:3.12-slim-bookworm` (`Dockerfile`); CI matrix covers 3.10, 3.11, 3.12 (`.github/workflows/ci.yml`); README advertises 3.12+.
- Async runtime: `asyncio` event loop used exclusively for CDP WebSocket sessions (`scripts/browser.py`), with synchronous `asyncio.run(...)` bridges from adapters and renderers (`adapters/x.py`, `adapters/linkedin.py`, `render/cards.py`, `render/carousel.py`).
- No application server, web framework, or long-running HTTP listener. Execution is CLI/cron/daemon driven.

**Package Manager:**
- `pip` with `venv` (`.venv` created by `setup.bat` / `setup.sh`)
- Dependency manifest: `requirements.txt` (minimum-version ranges only)
- Lockfile: missing (no `requirements.lock`, no `poetry.lock`, no `Pipfile.lock`)
- No packaging metadata: `setup.py` is an onboarding CLI dispatcher to `scripts/wizard.py`, not a distutils/setuptools package definition. No `pyproject.toml`.

## Frameworks

**Core:**
- Custom Chrome DevTools Protocol client - `scripts/browser.py` (HTTP `/json/*` discovery plus WebSocket `Session`; no Selenium, Playwright, or Puppeteer)
- Adapter framework - `adapters/base.py` defines `PlatformAdapter`, `PlatformCapabilities`, `PublishPayload`, `PublishResult`; implementations in `adapters/x.py`, `adapters/bluesky.py`, `adapters/linkedin.py`, `adapters/threads.py`, exported by `adapters/__init__.py`
- AT Protocol (ATProto) XRPC client - hand-rolled `urllib` client in `adapters/bluesky.py`
- Multi-provider LLM client - hand-rolled `urllib` REST client in `scripts/llm.py` (Gemini, OpenAI, Anthropic/Claude, OpenRouter)
- Visual render pipeline - `render/cards.py` (CDP `Page.captureScreenshot`), `render/carousel.py` (CDP `Page.printToPDF`), `render/infocard.py` (Pillow)
- Scheduling/orchestration - no scheduler library; `scripts/due.py` (jittered slot gate), `scripts/gate.py`, `scripts/autoposter.py`, `scripts/pipeline.py`, `scripts/daemon.py`

**Testing:**
- pytest >=8.0.0 - Test runner, configured in `pytest.ini` (`pythonpath = .`, `testpaths = tests`)
- pytest-asyncio >=0.23.0 - Declared in `requirements.txt`; asyncio is exercised largely through `unittest.mock.patch("...asyncio.run")` in tests
- `unittest.mock` - Patching browser, HTTP, and webhook boundaries (`tests/conftest.py`)
- 230 test functions across 31 files under `tests/`

**Build/Dev:**
- Docker - `Dockerfile` (Chromium, chromedriver, Xvfb, fonts, Python deps)
- Docker Compose - `docker-compose.yml` (single `omnipost` service, healthcheck, bind mounts, named browser-profile volume)
- GitHub Actions - `.github/workflows/ci.yml` (Ubuntu + Windows, Python 3.10-3.12, `pytest -v`)
- systemd - `systemd/omnipost.service` (VPS deployment via `scripts/run_vps.sh`)
- Windows Task Scheduler - `scripts/setup_scheduler.ps1` (daily pipeline at 11:00, autoposter every 10 minutes)
- `xvfb` - Virtual display `:99` for headless Chromium (`scripts/docker-entrypoint.sh`, `scripts/run_vps.sh`)

## Key Dependencies

**Critical:**
- `websockets>=12.0` - Sole transport for CDP WebSocket sessions; used in `scripts/browser.py` (`Session.__aenter__`). Drives every browser-based publish and render.
- `Pillow>=10.0.0` - Programmatic 1200x675 infocard PNG generation in `render/infocard.py`.

**Infrastructure:**
- `pyyaml>=6.0` - Declared for YAML validation; actually imported only by `tests/test_docker_config.py`
- `requests>=2.28.0` - Declared but not imported anywhere in `scripts/`, `adapters/`, `render/`, or `tests/`; runtime HTTP uses stdlib `urllib.request`
- `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` - Developer/test-only
- Python standard library modules doing heavy lifting: `urllib.request`, `urllib.parse`, `json`, `asyncio`, `subprocess`, `xml.etree.ElementTree`, `zoneinfo`, `hashlib`, `base64`, `pathlib`
- No database driver, no ORM, no HTTP framework, no cloud SDK, no telemetry SDK is installed.

## Configuration

**Environment:**
- `config.example.json` is the committed template; `config.json` is the per-install file (git-ignored via `.gitignore`) and is present in this workspace.
- `.env` is present in this workspace and is git-ignored. Existence noted only; contents were not read.
- Configuration is merged over hardcoded defaults in `scripts/settings.py` (`DEFAULTS`, `_merged`).
- Key config sections: `platforms` (`x`, `bluesky`, `linkedin`, `threads`), `slots`, `jitter_minutes`, `min_gap_hours`, `timezone`, `feeds`, `subreddits`, `x_queries`, `research_hour`, `window_hours`, `require_verified_source`, `browser` (`port`, `profile_dir`, `chrome_path`, `headless`), optional `llm` (`provider`, `model`).
- Runtime state lives in `state.json` (schema 2.0, managed by `scripts/ledger.py`), plans in `drafts/YYYY-MM-DD.json`, harvested items in `swipe/YYYY-MM-DD.json`, tick counter in `.tick`.
- Voice/profile guidance is read from `references/voice-profile.local.md` by `scripts/llm.py` and written by `scripts/feedback.py`; the file is git-ignored.
- Secrets are resolved from `os.environ` with a `.env` file fallback in `scripts/llm.py`, `scripts/notify_webhook.py`, and by the wizard in `scripts/wizard.py`.

**Build:**
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container image and entrypoint
- `docker-compose.yml` - Service, volumes, environment, healthcheck
- `.github/workflows/ci.yml` - CI test matrix
- `pytest.ini` - Test discovery and import path
- `systemd/omnipost.service` - Linux service unit
- `scripts/setup_scheduler.ps1` - Windows scheduled tasks
- No `tsconfig.json`, `.nvmrc`, `.python-version`, `Makefile`, `tox.ini`, or `pyproject.toml`.

## Platform Requirements

**Development:**
- Python 3.10+ with `pip` and `venv`
- A Chromium-family browser (Chrome, Chromium, or Microsoft Edge) discoverable by `scripts/settings.py:find_chrome`, or an explicit `browser.chrome_path`
- A dedicated browser profile directory (default `~/.omnipost/edge-profile`, legacy `~/.tweetytweets/edge-profile`)
- Local CDP debugging port (configured value; defaults differ by module: `9222` in `config.example.json`/`scripts/settings.py`, `9444` in `scripts/browser_daemon.py` and `adapters/x.py`)
- Write access to `drafts/`, `swipe/`, `shots/`, `scratch/`
- Optional: Docker + Docker Compose for containerized runs

**Production:**
- Docker: `python:3.12-slim-bookworm` + `chromium`, `chromium-driver`, `xvfb`, `fonts-liberation`, `fonts-dejavu-core`, `procps`, `curl`; entrypoint `scripts/docker-entrypoint.sh`, default command `python scripts/daemon.py`
- Linux VPS: Debian/Ubuntu, `chromium`, `xvfb`, `fonts-liberation`, `fonts-noto-color-emoji`, `git`, systemd (`scripts/deploy_vps.sh`, `systemd/omnipost.service`)
- Windows workstation: Chrome/Edge + PowerShell + optional Task Scheduler (`scripts/setup_scheduler.ps1`)
- Persistent storage: host files `config.json`, `state.json`, `drafts/`, `swipe/`, `scratch/` plus `omnipost_browser_data` volume for the browser profile (`docker-compose.yml`)

---

*Stack analysis: 2026-10-20*
