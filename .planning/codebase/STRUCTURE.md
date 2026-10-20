# Codebase Structure

**Analysis Date:** 2026-10-20

## Directory Layout

```text
TEST-TWEETYTWEET/
├── adapters/              # PlatformAdapter implementations (X, Bluesky, LinkedIn, Threads)
│   ├── __init__.py        # Package exports for all adapters + base contracts
│   ├── base.py            # ABC, capabilities, payload/result dataclasses, failure artifacts
│   ├── x.py               # X adapter (CDP via scripts/post.py)
│   ├── bluesky.py         # Bluesky adapter (ATProto XRPC, stdlib urllib)
│   ├── linkedin.py        # LinkedIn adapter (stealth CDP, ProseMirror, PDF/image attach)
│   └── threads.py         # Threads adapter (stealth CDP)
├── render/                # Visual asset generation
│   ├── __init__.py        # Public exports: infocard, carousel HTML/PDF
│   ├── cards.py           # 1–3 retina PNG cards via CDP screenshots
│   ├── carousel.py        # 1080×1080 HTML preview + vector PDF via Page.printToPDF
│   ├── infocard.py        # Pillow 1200×675 dark-mode PNG infocard
│   ├── card_template.html # Card markup/theme used by cards.py
│   └── template.html      # Carousel slide markup used by carousel.py
├── scripts/               # CLI modules: orchestration, scheduling, synthesis, diagnostics
│   ├── pipeline.py        # Daily harvest → synthesize → render → draft
│   ├── autoposter.py      # Due-slot dispatcher across active adapters
│   ├── daemon.py          # Long-running supervisor (pipeline + autoposter tick)
│   ├── due.py             # Jittered plan, due selection, fill/mark
│   ├── gate.py            # Zero-cost schedule gate (IDLE or JSON)
│   ├── cron_gate.py       # Plain-cron variant of the gate
│   ├── research.py        # HN / RSS / Reddit / X collectors
│   ├── generate.py        # Topic synthesis and carousel integrity
│   ├── llm.py             # Gemini/OpenAI/Claude/OpenRouter REST client
│   ├── repurpose.py       # Four platform-native formatters + media orchestration
│   ├── voice_profile.py   # Voice measurement and DO-NOT enforcement
│   ├── validator.py       # Credential probes + runtime guardrails
│   ├── ledger.py          # state.json schema v2.0 + atomic writes
│   ├── settings.py        # Merged config, browser discovery, adapter registry
│   ├── browser.py         # Minimal CDP websocket driver
│   ├── browser_daemon.py  # Browser lifecycle auto-healer
│   ├── post.py            # X composer automation, measurement, verification
│   ├── publish_now.py     # Immediate manual multi-platform publisher
│   ├── test_adapter.py    # Single-platform diagnostic harness
│   ├── analytics.py       # Engagement metric collection
│   ├── feedback.py        # Hook classification → voice-profile update
│   ├── notify.py          # Desktop toast + webhook facade
│   ├── notify_webhook.py  # Telegram/Discord dispatch + session alerts
│   ├── doctor.py          # Readiness checks and --healthcheck
│   ├── prereq_check.py    # Prerequisite checks + state file guard
│   ├── wizard.py          # 6-step onboarding ceremony
│   ├── setup_scheduler.ps1# Windows Task Scheduler registration
│   ├── deploy_vps.sh      # Ubuntu/Debian provisioning
│   ├── run_vps.sh         # systemd entrypoint, Xvfb + daemon
│   ├── docker-entrypoint.sh# Xvfb + bind-mount collision guard
│   └── launch_desktop_edge.py # Windows desktop Edge launcher
├── tests/                 # pytest suite (230 tests)
├── systemd/               # omnipost.service unit
├── docs/                  # Architecture blueprint + images + superpowers plans
├── drafts/                # Generated daily plans (git-ignored)
├── swipe/                 # Collected research items (git-ignored)
├── scratch/               # Generated cards, carousels, previews, operator notes (git-ignored)
├── shots/                 # Compose/profile/failure screenshots (git-ignored)
├── references/            # Voice profile template + local measured profile (local file git-ignored)
├── examples/              # Scheduling integration examples
├── .github/workflows/     # CI matrix (Ubuntu/Windows × Python 3.10–3.12)
├── .planning/             # GSD project state, requirements, roadmap, phase plans
├── .superpowers/          # SDD task briefs/reports
├── config.example.json    # Documented configuration template
├── config.json            # Live install configuration (git-ignored)
├── state.json             # Live publishing ledger (git-ignored)
├── .tick                  # Monotonic gate counter (git-ignored)
├── requirements.txt       # Runtime + test dependencies
├── pytest.ini             # pythonpath=. and testpaths=tests
├── Dockerfile             # python:3.12-slim + Chromium + Xvfb
├── docker-compose.yml     # Bind mounts, healthcheck, browser volume
├── setup.py               # Onboarding entrypoint → scripts/wizard.py
├── setup.bat / setup.sh   # One-click bootstrap scripts
└── README.md, SKILL.md, USERGUIDE.md, WALKTHROUGH.md, SECURITY.md
```

## Directory Purposes

**`adapters/`:**
- Purpose: One module per social platform behind the `PlatformAdapter` contract.
- Contains: Adapter classes, capability declarations, DOM/XRPC logic, verification.
- Key files: `adapters/base.py`, `adapters/x.py`, `adapters/bluesky.py`, `adapters/linkedin.py`, `adapters/threads.py`.

**`render/`:**
- Purpose: Local, dependency-light visual generation using Pillow and CDP.
- Contains: HTML templates, card slide builders, PDF/PNG renderers.
- Key files: `render/cards.py`, `render/carousel.py`, `render/infocard.py`, `render/card_template.html`, `render/template.html`.

**`scripts/`:**
- Purpose: All executable pipeline stages and operator commands.
- Contains: Orchestrators, schedule/ledger logic, content synthesis, browser driver, notifications, deployment scripts.
- Key files: `scripts/pipeline.py`, `scripts/autoposter.py`, `scripts/due.py`, `scripts/generate.py`, `scripts/repurpose.py`, `scripts/settings.py`, `scripts/ledger.py`, `scripts/browser.py`, `scripts/post.py`.

**`tests/`:**
- Purpose: Unit and integration coverage for adapters, pipeline, rendering, guardrails, onboarding, deployment.
- Contains: `test_*.py` modules plus shared webhook isolation fixture in `tests/conftest.py`.
- Key files: `tests/test_integration_e2e.py`, `tests/test_pipeline.py`, `tests/test_guardrails.py`, `tests/test_adapters.py`, `tests/test_validator.py`.

**`systemd/`:**
- Purpose: Linux service definition for the VPS deployment path.
- Contains: `systemd/omnipost.service`.
- Key files: `systemd/omnipost.service`.

**`docs/`:**
- Purpose: Long-form architecture/expansion documentation and image assets.
- Contains: `docs/EXPANSION_BLUEPRINT_MULTI_PLATFORM.md`, `docs/images/*.jpg`, `docs/superpowers/plans/`.
- Key files: `docs/EXPANSION_BLUEPRINT_MULTI_PLATFORM.md`.

**`drafts/`:**
- Purpose: Daily plan files consumed by `autoposter` and `publish_now`.
- Contains: `YYYY-MM-DD.json` documents with slot-level platform variants.
- Key files: `drafts/2026-10-20.json` (current shape reference).

**`swipe/`:**
- Purpose: Normalized research intake.
- Contains: `YYYY-MM-DD.json`; may be empty until `scripts/research.py collect` runs.
- Key files: none committed (directory is git-ignored).

**`scratch/`:**
- Purpose: Disposable generated assets and operator working files.
- Contains: `scratch/cards/`, `scratch/carousels/`, `scratch/infocards/`, preview HTML, diagnostic scripts.
- Key files: `scratch/cards/`, `scratch/carousels/`, `scratch/post.txt`.

**`shots/`:**
- Purpose: Visual verification and failure evidence.
- Contains: `compose.png`, `profile.png`, `<platform>_fail.png`, `<platform>_fail.html`.
- Key files: `shots/compose.png`, `shots/profile.png`.

**`references/`:**
- Purpose: Voice-profile guidance for synthesis.
- Contains: `references/README.md` (template) and `references/voice-profile.local.md` (measured profile, git-ignored).
- Key files: `references/README.md`, `references/voice-profile.local.md`.

**`examples/`:**
- Purpose: Integration recipes for external schedulers/agents.
- Contains: `examples/scheduling.md`.

**`.github/workflows/`:**
- Purpose: CI.
- Contains: `ci.yml` running the full suite on a 6-cell OS/Python matrix.

**`.planning/` and `.superpowers/`:**
- Purpose: GSD planning artifacts and SDD task history.
- Contains: `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `phases/*`, task briefs/reports.
- Key files: `.planning/PROJECT.md`, `.planning/ROADMAP.md`.

## Key File Locations

**Entry Points:**
- `setup.py`: Onboarding dispatcher to `scripts/wizard.py` (`setup.py:18`).
- `scripts/daemon.py`: Container/systemd supervisor (`scripts/daemon.py:21`).
- `scripts/pipeline.py`: Daily generation pipeline (`scripts/pipeline.py:67`).
- `scripts/autoposter.py`: Scheduled dispatch loop body (`scripts/autoposter.py:62`).
- `scripts/gate.py`: Schedule gate for external cron (`scripts/gate.py:92`).
- `scripts/publish_now.py`: Manual immediate publish (`scripts/publish_now.py:47`).
- `scripts/post.py`: X-only CLI and automation core (`scripts/post.py:553`).
- `render/carousel.py`: `python -m render.carousel` proofing (`render/carousel.py:471`).
- `render/cards.py`: `python -m render.cards --test` (`render/cards.py:235`).

**Configuration:**
- `config.example.json`: Documented template for all settings.
- `config.json`: Live install config (git-ignored; merged over defaults by `scripts/settings.py:95`).
- `.env`: Present in repo root — contains environment configuration; contents not inspected.
- `scripts/settings.py`: Defaults, merge logic, browser discovery, adapter registry.
- `pytest.ini`: `pythonpath = .`, `testpaths = tests`.
- `requirements.txt`: `websockets`, `Pillow`, `pyyaml`, `requests`, `pytest`, `pytest-asyncio`.
- `Dockerfile`, `docker-compose.yml`: Container build, mounts, healthcheck.
- `systemd/omnipost.service`: systemd unit.
- `scripts/setup_scheduler.ps1`: Windows scheduled tasks.

**Core Logic:**
- `scripts/due.py`: Jittered plan, due selection, fill/mark commands.
- `scripts/ledger.py`: Ledger migration, atomic save, per-platform status.
- `scripts/generate.py`: Deterministic topic synthesis + carousel integrity.
- `scripts/llm.py`: Provider/model/key resolution and REST calls.
- `scripts/repurpose.py`: X/Bluesky/LinkedIn/Threads formatters and media orchestration.
- `scripts/validator.py`: Credential probes and runtime guardrails.
- `scripts/browser.py`: CDP transport (tabs, sessions, screenshots).
- `adapters/base.py`: The platform port and DTOs.
- `render/cards.py`: PNG card generation.
- `render/carousel.py`: PDF carousel generation.

**Testing:**
- `tests/conftest.py`: Autouse webhook isolation fixture.
- `tests/test_integration_e2e.py`: Research → repurpose → dispatch → ledger simulation.
- `tests/test_pipeline.py`: Pipeline orchestration with mocked generation/repurpose.
- `tests/test_guardrails.py`: Runtime safety rules.
- `tests/test_adapters.py` / `tests/test_multi_platform.py`: Adapter contract and multi-platform dispatch.
- `tests/test_vps_deployment.py` / `tests/test_docker_config.py`: Deployment config assertions.

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (`autoposter.py`, `browser_daemon.py`, `voice_profile.py`).
- Adapters: platform name only (`x.py`, `bluesky.py`, `linkedin.py`, `threads.py`).
- Tests: `test_<subject>.py` (`test_linkedin_carousel.py`, `test_retry_isolation.py`).
- Markdown docs: `UPPERCASE.md` at root (`README.md`, `SECURITY.md`) and in `.planning/codebase/`; lowercase/hyphenated under `docs/`.
- Shell scripts: `snake_case.sh` (`deploy_vps.sh`, `run_vps.sh`).
- Generated drafts/swipe: `YYYY-MM-DD.json`.
- Generated cards: `card_<YYYYMMDD>_<HHMM>_card_<N>.png` (`scripts/repurpose.py:152`).

**Directories:**
- Lowercase, plural or domain-named: `adapters/`, `render/`, `scripts/`, `tests/`, `drafts/`, `swipe/`, `shots/`.
- Planning dirs are dot-prefixed: `.planning/`, `.superpowers/`.

**Python symbols:**
- Classes: `PascalCase` (`PlatformAdapter`, `BlueskyAdapter`, `GuardRailError`).
- Functions/variables: `snake_case` (`ensure_browser_running`, `validate_draft_guardrails`).
- Private helpers: leading underscore (`_open`, `_norm`, `_async_publish`).
- Module constants: `UPPER_SNAKE_CASE` (`MAX_LAG_HOURS`, `DEFAULT_MODELS`, `STEALTH_JS`).
- Platform keys: lowercase strings matching `platform_name` (`"x"`, `"bluesky"`, `"linkedin"`, `"threads"`).

## Where to Add New Code

**New Platform Adapter:**
- Implementation: create `adapters/<platform>.py` subclassing `PlatformAdapter` from `adapters/base.py`.
- Registration: add an `enabled` branch in `scripts/settings.get_active_adapters` (`scripts/settings.py:289`) and export it in `adapters/__init__.py:2`.
- Config: add a `platforms.<platform>` block to `scripts/settings.py:60-81` and `config.example.json`.
- Tests: add `tests/test_<platform>.py` following `tests/test_bluesky.py` / `tests/test_threads.py`.
- Registry maps used by diagnostics also need updating: `scripts/test_adapter.py:35-40`.

**New Pipeline Stage:**
- Primary code: a new `scripts/<stage>.py` with a `main()` and importable function, then call it from `scripts/pipeline.py` or `scripts/autoposter.py`.
- Tests: `tests/test_<stage>.py`; mock CDP and HTTP boundaries rather than hitting the network.
- Output contract: write into `drafts/`, `swipe/`, or `scratch/`, never into a new top-level state file unless it is added to `.gitignore`.

**New Content Formatter:**
- Implementation: add `format_<platform>` in `scripts/repurpose.py` and include it in `repurpose_topic` (`scripts/repurpose.py:101-213`).
- Tests: `tests/test_repurposer.py`, asserting the platform character ceiling.

**New Visual Renderer:**
- Implementation: add `render/<name>.py` and export it from `render/__init__.py`.
- Tests: `tests/test_<name>.py`; avoid requiring a live browser in unit tests (mock `_render_pdf_cdp` / `_capture_card_png`).
- Assets: place HTML templates next to the renderer in `render/`.

**New Scheduler / Gate Mode:**
- Implementation: extend `scripts/gate.py` or `scripts/cron_gate.py`, keeping the `IDLE\n` / JSON stdout contract.
- Tests: `tests/test_gate.py`.

**New Notification Channel:**
- Implementation: add a dispatcher in `scripts/notify_webhook.py` and route it through `dispatch_webhook` (`scripts/notify_webhook.py:215`).
- Tests: `tests/test_notify_webhook.py`.

**Utilities:**
- Shared helpers: `scripts/settings.py` for configuration/paths, `scripts/ledger.py` for state, `scripts/browser.py` for CDP. Do not create a generic `utils.py`; keep helpers in the owning module.

## Special Directories

**`drafts/`:**
- Purpose: Daily execution plans.
- Generated: Yes (`scripts/due.py:96-97`, `scripts/pipeline.py:102`).
- Committed: No (`.gitignore:8`).

**`swipe/`:**
- Purpose: Raw research intake.
- Generated: Yes (`scripts/research.py:330-372`).
- Committed: No (`.gitignore:7`).

**`scratch/`:**
- Purpose: Generated media, previews, and operator test scripts.
- Generated: Yes.
- Committed: No (`.gitignore:10`).

**`shots/`:**
- Purpose: Verification screenshots and failure artifacts.
- Generated: Yes (`scripts/post.py:412`, `adapters/base.py:45-48`).
- Committed: No (`.gitignore:9`).

**`references/`:**
- Purpose: Voice guidance. `references/voice-profile.local.md` is machine-local and may contain personal writing samples.
- Generated: Partially (`scripts/voice_profile.py:330-335`, `scripts/feedback.py:123-164`).
- Committed: Only `references/README.md`; the local profile is git-ignored (`.gitignore:13`).

**`docs/images/`:**
- Purpose: README/architecture imagery.
- Generated: No.
- Committed: Yes.

**`.planning/`:**
- Purpose: GSD project memory (requirements, roadmap, phases, codebase map).
- Generated: Yes (by GSD commands).
- Committed: Yes.

**`.superpowers/`:**
- Purpose: SDD task briefs and execution reports.
- Generated: Yes.
- Committed: Yes (currently tracked).

**`__pycache__/`, `.pytest_cache/`, `.venv/`:**
- Purpose: Python/test/tooling caches.
- Generated: Yes.
- Committed: No (`.gitignore:21-29`).

**Browser profiles (`~/.omnipost/edge-profile`, legacy `~/.tweetytweets/edge-profile`):**
- Purpose: Persistent cookies and sessions for CDP platforms. Outside the repo; never committed.
- Generated: Yes, on first browser launch (`scripts/settings.py:126-156`).
- Committed: No.

---

*Structure analysis: 2026-10-20*
