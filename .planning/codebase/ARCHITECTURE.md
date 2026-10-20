<!-- refreshed: 2026-10-20 -->
# Architecture

**Analysis Date:** 2026-10-20

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                    TRIGGERS / INTERFACES                             │
│  `scripts/daemon.py`   `scripts/pipeline.py`   `scripts/autoposter.py`│
│  `scripts/gate.py`     `scripts/cron_gate.py`  `scripts/publish_now.py`│
│  `scripts/post.py`     `setup.py` → `scripts/wizard.py`               │
└──────────┬───────────────────────┬───────────────────────┬───────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────────┐
│  SCHEDULE / GATE    │  │  INTELLIGENCE       │  │  CHANNEL ADAPTERS  │
│  `scripts/due.py`   │  │  `scripts/research.py`│ │  `adapters/*.py`   │
│  `scripts/ledger.py`│  │  `scripts/generate.py`│ │  `scripts/post.py` │
│  `.tick` counter    │  │  `scripts/llm.py`     │ │  `scripts/browser.py`│
│                     │  │  `scripts/repurpose.py`│ │  `scripts/browser_daemon.py`│
└──────────┬──────────┘  └──────────┬────────────┘ └─────────┬──────────┘
           │                        │                        │
           │                        ▼                        │
           │             ┌─────────────────────┐             │
           │             │  VISUAL ENGINE      │             │
           │             │  `render/cards.py`  │             │
           │             │  `render/carousel.py`│            │
           │             │  `render/infocard.py`│            │
           │             └──────────┬──────────┘             │
           │                        │                        │
           ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FILE-BACKED STATE & OUTPUTS                       │
│  `state.json` (ledger v2.0)   `drafts/YYYY-MM-DD.json`               │
│  `swipe/YYYY-MM-DD.json`      `scratch/`   `shots/`                   │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  NOTIFY / OBSERVE: `scripts/notify.py`, `scripts/notify_webhook.py`, │
│  `scripts/analytics.py`, `scripts/feedback.py`, `scripts/doctor.py`   │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Daemon supervisor | Wakes the pipeline at 11:00+ and runs an autoposter tick every 5 minutes | `scripts/daemon.py` |
| Daily pipeline | Harvest → plan → synthesize → render → write `drafts/YYYY-MM-DD.json` | `scripts/pipeline.py` |
| Autoposter | Decide if a slot is due, dispatch every enabled adapter, record per-platform outcomes | `scripts/autoposter.py` |
| Schedule gate | Deterministic due-slot selection and the `IDLE`/JSON stdout contract | `scripts/due.py`, `scripts/gate.py`, `scripts/cron_gate.py` |
| Research collector | Normalize HN, RSS, Reddit, and X results into `swipe/YYYY-MM-DD.json` | `scripts/research.py` |
| Synthesis engine | Turn swipe items into a structured topic (LLM or deterministic heuristic) | `scripts/generate.py`, `scripts/llm.py` |
| Polymorphic repurposer | Reshape one topic into X, Bluesky, LinkedIn, and Threads copy plus media | `scripts/repurpose.py` |
| Visual engine | Render 1–3 retina PNG cards and optional 1080×1080 vector PDF carousels over CDP | `render/cards.py`, `render/carousel.py`, `render/infocard.py` |
| Adapter contract | `PlatformAdapter` ABC, `PlatformCapabilities`, `PublishPayload`, `PublishResult` | `adapters/base.py` |
| Adapter registry | Instantiate only the enabled platform adapters from config | `scripts/settings.py` (`get_active_adapters`) |
| X adapter | CDP composer automation, read-back profile verification | `adapters/x.py`, `scripts/post.py` |
| Bluesky adapter | Native ATProto XRPC session, blob upload, record create/get | `adapters/bluesky.py` |
| LinkedIn adapter | Stealth CDP ProseMirror automation, 4-hour rate guard, toast URN/activity verification | `adapters/linkedin.py` |
| Threads adapter | Stealth CDP composer automation, profile read-back verification | `adapters/threads.py` |
| CDP transport | Minimal websocket driver, tab reuse, navigation settling, screenshots | `scripts/browser.py` |
| Browser auto-healer | Keep the automation browser alive on the configured debugging port | `scripts/browser_daemon.py` |
| State ledger | Schema v2.0 migration, atomic writes, per-platform status queries | `scripts/ledger.py` |
| Guardrails | Enforcement-first draft validation and credential probes | `scripts/validator.py` |
| Configuration | Merged `config.json` defaults, browser discovery, char ceiling, timezone | `scripts/settings.py` |
| Onboarding | 6-step interactive/non-interactive setup, live credential probes | `scripts/wizard.py`, `setup.py` |
| Notifications | Desktop toast, Telegram, Discord, session-expiry alerts, summary cards | `scripts/notify.py`, `scripts/notify_webhook.py` |
| Analytics/feedback | Scrape engagement metrics, classify hooks, rewrite the voice profile | `scripts/analytics.py`, `scripts/feedback.py` |

## Pattern Overview

**Overall:** Layered batch pipeline with ports-and-adapters at the publishing boundary, coordinated through a file-backed atomic ledger.

**Key Characteristics:**
- Every stage is a standalone CLI module under `scripts/`, callable directly or by `scripts/daemon.py`; there is no web server or long-lived application object.
- Platforms implement the `PlatformAdapter` port in `adapters/base.py:67`; orchestration depends only on `PublishPayload`/`PublishResult`, never on platform internals.
- Two separate execution surfaces: a synchronous orchestrator (`autoposter.py`, `publish_now.py`) and asynchronous CDP sessions bridged with `asyncio.run(...)` inside each adapter (for example `adapters/x.py:66`, `adapters/linkedin.py:654`).
- All durable state is JSON on disk: `state.json`, `drafts/*.json`, `swipe/*.json`, `.tick`. Writes to `state.json` use temp-file replacement (`scripts/ledger.py:113`).
- Verification is a first-class stage: X reads the profile timeline (`scripts/post.py:361`), Bluesky calls `getRecord` (`adapters/bluesky.py:320`), LinkedIn reads recent activity (`adapters/linkedin.py:662`), Threads reads the profile (`adapters/threads.py:423`).
- Consumer hooks are optional: an external cron monitor can consume `gate.py`/`cron_gate.py` instead of running the internal daemon.

## Layers

**Interface / Orchestration:**
- Purpose: Accept human or scheduler intent and sequence the pipeline.
- Location: `scripts/pipeline.py`, `scripts/autoposter.py`, `scripts/daemon.py`, `scripts/publish_now.py`, `setup.py`
- Contains: argparse entry points, subprocess fan-out, per-run summaries.
- Depends on: schedule layer, synthesis layer, adapter registry.
- Used by: Windows Task Scheduler (`scripts/setup_scheduler.ps1`), systemd (`systemd/omnipost.service`), Docker (`Dockerfile`), operators.

**Schedule / State:**
- Purpose: Decide what is due, prevent duplicates, and persist outcomes.
- Location: `scripts/due.py`, `scripts/gate.py`, `scripts/cron_gate.py`, `scripts/ledger.py`
- Contains: jittered plan creation, stale-slot retirement, guardrail gate, atomic ledger, schema migration.
- Depends on: `scripts/settings.py`, `scripts/validator.py`, `state.json`, `drafts/`.
- Used by: `scripts/autoposter.py`, cron monitors, `scripts/analytics.py`, `scripts/feedback.py`.

**Intelligence / Synthesis:**
- Purpose: Convert raw signals into platform-native copy.
- Location: `scripts/research.py`, `scripts/generate.py`, `scripts/llm.py`, `scripts/repurpose.py`, `scripts/voice_profile.py`
- Contains: source collectors, heuristic topic synthesis, multi-provider REST LLM calls, four platform formatters, voice measurement.
- Depends on: `swipe/`, `references/voice-profile.local.md`, provider credentials in environment or `.env`.
- Used by: `scripts/pipeline.py`, `scripts/publish_now.py --fresh`.

**Visual Engine:**
- Purpose: Produce local images/documents without a cloud renderer.
- Location: `render/cards.py`, `render/carousel.py`, `render/infocard.py`, `render/card_template.html`, `render/template.html`
- Contains: HTML templating, Pillow infocards, CDP `Page.captureScreenshot` and `Page.printToPDF`.
- Depends on: `scripts/browser.py`, the automation browser.
- Used by: `scripts/repurpose.py`, `python -m render.carousel`, tests.

**Channel Adapters:**
- Purpose: Publish and verify on one platform.
- Location: `adapters/x.py`, `adapters/bluesky.py`, `adapters/linkedin.py`, `adapters/threads.py`
- Contains: platform-specific auth/session logic, DOM or XRPC calls, verification.
- Depends on: `adapters/base.py`, `scripts/browser.py`, `scripts/post.py` (X only), `scripts/settings.py`.
- Used by: `scripts/autoposter.py`, `scripts/publish_now.py`, `scripts/test_adapter.py`.

**Configuration / Notifications / Diagnostics:**
- Purpose: Make the pipeline installable and observable.
- Location: `scripts/settings.py`, `scripts/wizard.py`, `scripts/validator.py`, `scripts/notify.py`, `scripts/notify_webhook.py`, `scripts/doctor.py`, `scripts/prereq_check.py`
- Contains: merged config, onboarding interview, live probes, webhook dispatch, health checks.
- Depends on: `config.json`, environment variables, `.env` (presence only).
- Used by: every layer.

## Data Flow

### Primary Request Path — Scheduled Publish Tick

1. Trigger: Docker runs `python scripts/daemon.py` as the container command (`Dockerfile:33`); systemd runs `scripts/run_vps.sh`, which execs the same daemon (`systemd/omnipost.service:11`, `scripts/run_vps.sh:27`); Windows registers `scripts/autoposter.py` every 10 minutes (`scripts/setup_scheduler.ps1:22`).
2. Daemon loop: if the date changed and the hour is ≥ 11, or today's plan is missing, run `scripts/pipeline.py`; then always run `scripts/autoposter.py` (`scripts/daemon.py:38-46`).
3. Pipeline health: ensure the CDP browser is up (`scripts/pipeline.py:73`), load `swipe/YYYY-MM-DD.json` (`scripts/pipeline.py:76`), and fall back to Hacker News when empty (`scripts/pipeline.py:84`).
4. Plan creation: if `drafts/YYYY-MM-DD.json` is absent, `due.make_plan` assigns each configured slot a jittered `due_at` (`scripts/due.py:65-98`).
5. Content fill: for each slot, `generate.generate_topic_from_items` (`scripts/pipeline.py:48`) tries the configured LLM (`scripts/generate.py:416-424`), else the deterministic heuristic (`scripts/generate.py:426`), then enforces a four-slide carousel shape (`scripts/generate.py:73`).
6. Repurposing and rendering: `repurpose.repurpose_topic` formats four texts (`scripts/repurpose.py:22-98`) and renders 1–3 PNG cards through `generate_topic_cards` (`scripts/repurpose.py:155-166`, `render/cards.py:192`), falling back to a Pillow infocard (`scripts/repurpose.py:169-184`).
7. Persist draft: the plan is rewritten with `slot.text`, `slot.headline`, `slot.image`, and `slot.platforms` (`scripts/pipeline.py:58-62`, `scripts/pipeline.py:102`).
8. Due check: `autoposter` shells out to `due.py check` (`scripts/autoposter.py:70`). `due()` scans today/yesterday plans, skips posted ledger slots, retires slots older than 6 hours, and runs guardrails (`scripts/due.py:147-195`).
9. Adapter selection: `settings.get_active_adapters` instantiates only enabled platforms (`scripts/settings.py:289-320`).
10. Per-platform dispatch: for each adapter, skip if already published in the ledger (`scripts/autoposter.py:142`), choose tailored text/media (`scripts/autoposter.py:151-159`), enforce `capabilities.max_characters` (`scripts/autoposter.py:169-172`), and call `adapter.publish(payload)` (`scripts/autoposter.py:186`).
11. Adapter internals:
    - X: `post.do_post` opens the composer, validates guardrails, inserts text with `Input.insertText`, clicks Post, then polls the profile (`adapters/x.py:66`, `scripts/post.py:434-517`).
    - Bluesky: `createSession` → optional `uploadBlob` → `com.atproto.repo.createRecord` → `getRecord` verification (`adapters/bluesky.py:175-341`).
    - LinkedIn: stealth CDP, rate-limit guard, ProseMirror input, optional document/image attach, toast URN + activity read-back (`adapters/linkedin.py:217-241`, `adapters/linkedin.py:651`, `adapters/linkedin.py:662`).
    - Threads: stealth CDP composer, media attach, profile read-back (`adapters/threads.py:412-467`).
12. Record and notify: `ledger.record_platform_status` writes the per-platform outcome atomically (`scripts/autoposter.py:187`, `scripts/ledger.py:161-222`), then `notify.notify_publish` sends toast/Telegram/Discord (`scripts/autoposter.py:208`, `scripts/notify.py:47`).
13. Completion: if every target platform is published, `due.py mark` flips `slot.posted` and stores a primary URL (`scripts/autoposter.py:212-216`). Otherwise the slot remains pending and is retried on the next tick.

### Secondary Flow — Manual Immediate Publish

1. Operator runs `python scripts/publish_now.py --text ...`, `--draft ...`, `--slot ...`, or `--fresh`.
2. With `--fresh`, the full pipeline runs first (`scripts/publish_now.py:68-74`).
3. Platform-tailored text/media is extracted from `drafts/*.json` (`scripts/publish_now.py:112-135`).
4. Connectivity is probed (`scripts/publish_now.py:37-44`, `scripts/publish_now.py:208`), then each adapter publishes inside a single-worker `ThreadPoolExecutor` with an 80-second default timeout (`scripts/publish_now.py:245-247`).
5. Each result is recorded in the ledger and failures trigger a webhook (`scripts/publish_now.py:250-288`).

### Secondary Flow — Research Only

1. `python scripts/research.py collect` collects HN, RSS, Reddit, and X candidates (`scripts/research.py:330-352`).
2. Items are deduped and ranked (`scripts/research.py:354-361`) and returned as `{generated_at, window_hours, counts, status, items}` (`scripts/research.py:362-372`).
3. The CLI writes the result to `swipe/YYYY-MM-DD.json`.

### Secondary Flow — Onboarding

1. `setup.py` dispatches to `scripts/wizard.py:main` (`setup.py:18`).
2. The wizard interviews for handles, LLM provider/model, voice, timezone, webhooks, and dry-run mode (`scripts/wizard.py:139`).
3. Live probes validate Bluesky credentials, LLM keys/model IDs, and webhooks (`scripts/validator.py:48-286`).
4. It writes `config.json` and `.env` (secrets only) and calls `guarantee_state_files` to create `state.json`, `drafts/`, `swipe/`, `scratch/` (`scripts/prereq_check.py:27-50`).

### Secondary Flow — Analytics / Feedback Loop

1. `scripts/analytics.py` loads the ledger, selects recent published posts, fetches Bluesky public XRPC metrics and X syndication metrics, and saves metrics back into each platform record (`scripts/analytics.py:107-150`).
2. `scripts/feedback.py` classifies hooks, computes an engagement score, and appends/replaces the "Learned Algorithmic Preferences" section in `references/voice-profile.local.md` (`scripts/feedback.py:56-164`).
3. The next synthesis run loads that profile via `scripts/llm.py:159`.

**State Management:**
- Ledger: `state.json` schema v2.0 (`scripts/ledger.py:28`), auto-migrated from v1 (`scripts/ledger.py:31-83`), atomically written through a PID-tagged temp file (`scripts/ledger.py:113-121`).
- Ledger record shape: `{version, handle, ai_update_day, last_ai_update, posts:[{date, slot, kind, at, text, platforms:{<platform>:{status, url, verified, at, error, metrics?}}}]}`.
- Daily plan shape: `{date, created_at, handle, slots:[{slot, kind, due_at, text, image, posted, tweet_url, headline, platforms:{x, bluesky, linkedin, threads:{enabled, text, media, media_type, document_title?}}}]}`.
- Idle counter: `.tick` is a monotonic integer used to make a due payload differ from the previous tick (`scripts/due.py:198-207`).
- Per-process cache: Bluesky keeps `_session_cache` for the lifetime of one adapter instance (`adapters/bluesky.py:121`). No other shared in-memory cache exists.

## Key Abstractions

**`PlatformAdapter` port:**
- Purpose: Isolate every platform behind one synchronous contract (`platform_name`, `capabilities`, `check_session`, `publish`, `verify`).
- Examples: `adapters/x.py:14`, `adapters/bluesky.py:91`, `adapters/linkedin.py:191`, `adapters/threads.py:152`
- Pattern: Abstract base class + per-platform capability declaration + normalized result object.

**`PublishPayload` / `PublishResult` DTOs:**
- Purpose: Carry text, media paths, media type, and metadata in; carry success, URL, verification, and raw response out.
- Examples: `adapters/base.py:19-40`
- Pattern: Dataclasses at the boundary; adapters never leak platform JSON into orchestration.

**Daily polymorphic draft:**
- Purpose: One slot carries four fully written platform variants plus shared media, so publishing never re-writes copy.
- Examples: `drafts/2026-10-20.json`, produced by `scripts/repurpose.py:188-213`
- Pattern: Content-addressed by date + slot; `posted`/`tweet_url` are the plan-side completion flags.

**Atomic ledger:**
- Purpose: Single source of truth for what actually published, per platform and per slot.
- Examples: `scripts/ledger.py:86-222`
- Pattern: Read-modify-write with OS-level replace; queries (`is_platform_done`, `get_pending_platforms`) let the orchestrator resume after partial failure.

**CDP `Session`:**
- Purpose: Thin request/response wrapper over a Chrome DevTools websocket, with `eval`, `goto`, and navigation settling.
- Examples: `scripts/browser.py:122-172`, `scripts/browser.py:174-227`
- Pattern: Context manager, one websocket per page session, no Selenium/Playwright layer.

**Schedule gate contract:**
- Purpose: Make idle ticks free and retries reliable.
- Examples: `scripts/due.py:253-259`, `scripts/gate.py:39-58`, `scripts/cron_gate.py:40-71`
- Pattern: `IDLE\n` means "do nothing"; JSON with an incrementing `tick` means "wake and publish".

**LLM provider resolution:**
- Purpose: Choose provider/model/key without adding SDK dependencies.
- Examples: `scripts/llm.py:129-156`, `scripts/llm.py:353-477`
- Pattern: Explicit argument > environment/`.env` > `config.json` > inferred key > `local` deterministic fallback.

## Entry Points

**`python setup.py` / `python setup.py --non-interactive`:**
- Location: `setup.py:18`, `scripts/wizard.py:621`
- Triggers: Manual onboarding, `setup.bat`, `setup.sh`, `scripts/deploy_vps.sh:57`.
- Responsibilities: Write `config.json`/`.env`, validate credentials, guarantee state files.

**`python scripts/daemon.py`:**
- Location: `scripts/daemon.py:21`
- Triggers: Container `CMD` (`Dockerfile:33`), systemd via `scripts/run_vps.sh:27`.
- Responsibilities: Daily pipeline scheduling and a continuous autoposter loop.

**`python scripts/pipeline.py`:**
- Location: `scripts/pipeline.py:67`
- Triggers: Daemon (`scripts/daemon.py:41`), `publish_now.py --fresh`, Task Scheduler (`scripts/setup_scheduler.ps1:17`).
- Responsibilities: Produce a fully populated daily draft and its visual assets.

**`python scripts/autoposter.py`:**
- Location: `scripts/autoposter.py:62`
- Triggers: Daemon every 300 seconds, Task Scheduler every 10 minutes, manual runs.
- Responsibilities: Due check, multi-platform dispatch, ledger recording, completion marking.

**`python scripts/gate.py` / `python scripts/cron_gate.py`:**
- Location: `scripts/gate.py:92`, `scripts/cron_gate.py:40`
- Triggers: External cron/systemd timer/monitor.
- Responsibilities: Emit `IDLE` or a due payload; `cron_gate --wake` emits an agent instruction block.

**`python scripts/publish_now.py`:**
- Location: `scripts/publish_now.py:47`
- Triggers: Manual immediate publish.
- Responsibilities: Dispatch a single text or an existing draft to selected platforms.

**`python scripts/post.py`:**
- Location: `scripts/post.py:553`
- Triggers: Manual X-only operation and the `XAdapter`.
- Responsibilities: Session check, composer dry-run, measured character ceiling, post, verify, screenshots.

**`python scripts/test_adapter.py`:**
- Location: `scripts/test_adapter.py:69`
- Triggers: Manual per-platform diagnostics.
- Responsibilities: Publish one platform in isolation and surface failure artifacts.

**`python -m render.carousel` / `python -m render.cards`:**
- Location: `render/carousel.py:471`, `render/cards.py:235`
- Triggers: Manual visual proofing.
- Responsibilities: Build HTML previews, PDF carousels, and PNG cards.

**`python scripts/research.py`:**
- Location: `scripts/research.py:375`
- Triggers: Manual collection, Hermes planning job, pipeline fallback.
- Responsibilities: Write normalized swipe intelligence.

**`python scripts/doctor.py` / `python scripts/prereq_check.py`:**
- Location: `scripts/doctor.py:128`, `scripts/prereq_check.py:162`
- Triggers: Docker healthcheck (`docker-compose.yml:21`), preflight.
- Responsibilities: Report missing config/browser/dependencies and optionally test live connectivity.

## Architectural Constraints

- **Threading:** No shared event loop. Adapters are synchronous and call `asyncio.run(...)` per operation (`adapters/x.py:66`, `adapters/linkedin.py:654`, `adapters/threads.py:415`). `autoposter` publishes platforms sequentially (`scripts/autoposter.py:132`); `publish_now` wraps each adapter in a one-worker thread only to enforce a timeout (`scripts/publish_now.py:245`).
- **Single browser/profile:** All CDP platforms share one debugging port and one dedicated profile directory (`scripts/browser.py:73-119`, `scripts/settings.py:126-156`). There is no per-platform browser isolation; concurrency would contend for the same profile.
- **Global state:** `settings.load()` reads and merges `config.json` on every call; there is no config cache (`scripts/settings.py:95-110`). The ledger is a single global `state.json` (`scripts/ledger.py:27`). `.tick` is global (`scripts/due.py:47`).
- **Package import coupling:** `adapters/__init__.py` eagerly imports all four adapters and `scripts/post.py` (`adapters/__init__.py:2-12`). Importing `adapters.base` therefore loads the entire adapter package; lazy imports in `settings.get_active_adapters` (`scripts/settings.py:295-318`) are the only reason this does not create a hard cycle.
- **Bootstrapping:** Nearly every module mutates `sys.path` and uses a `try: from scripts import X / except ImportError: import X` fallback (for example `scripts/pipeline.py:20-35`, `scripts/due.py:30-40`, `scripts/autoposter.py:23-37`). Modules work whether launched as `python scripts/foo.py` or `python -m scripts.foo`.
- **Character ceiling invariant:** X posts require a measured ceiling before publishing (`scripts/validator.py:351-387`); non-X platforms use fixed protocol maxima (Bluesky 300, LinkedIn 3000, Threads 500 from `capabilities`).
- **Verification invariant:** A platform is recorded as published only from a `PublishResult`; slot completion additionally requires the ledger to report every target platform as `published` (`scripts/due.py:118-144`, `scripts/ledger.py:148-158`).
- **Time semantics:** All slot interpretation uses `settings.tzinfo()` (`scripts/due.py:53`). Slots are anchors plus random jitter, with a minimum gap (`scripts/due.py:65-98`). A slot more than 6 hours late is retired, never posted (`scripts/due.py:49`, `scripts/due.py:167-171`).
- **No database / no queue:** Coordination is entirely filesystem-based JSON and subprocess calls.
- **Secrets boundary:** Browser cookies live in the external profile directory, Bluesky uses an app-password environment variable, and `.env` is present in the repo root (existence only; contents not inspected).

## Anti-Patterns

### Dual `state.json` writers with different atomicity guarantees

**What happens:** `scripts/ledger.py:113` writes atomically via a temp file, but the legacy X path has its own `load_state`/`save_state` that writes `state.json` directly (`scripts/post.py:72-79`) and appends a flat post entry (`scripts/post.py:520-537`).
**Why it's wrong:** A crash during `post.py` can corrupt the same ledger that the rest of the system advertises as crash-safe, and the two writers produce different record shapes (`platforms` map vs flat `tweet_url`).
**Do this instead:** Route all state mutations through `scripts/ledger.py` (`load_state`, `record_platform_status`, `save_state`) and let its migration layer handle legacy records (`scripts/ledger.py:31-83`).

### Configuration default drift for the CDP port

**What happens:** `DEFAULTS["browser"]["port"]` is `9222` (`scripts/settings.py:55`) and `config.example.json:62` repeats it, while the daemon and adapters fall back to `9444` (`scripts/browser_daemon.py:26`, `adapters/x.py:20`, `adapters/linkedin.py:197`, `adapters/threads.py`), and the README documents `9444`.
**Why it's wrong:** A fresh install without `browser.port` produces a browser on 9222 but adapter/daemon code paths that assume 9444, yielding "browser not running" failures that look like auth failures.
**Do this instead:** Define the port once (for example in `scripts/settings.py`) and have `browser_daemon`, adapters, and renderers call that accessor instead of embedding their own fallback.

### Eager imports in the adapter package

**What happens:** `adapters/__init__.py:2-12` imports every adapter and its heavy dependencies at package import time, so `from adapters.base import PublishResult` in `scripts/ledger.py:25` loads X/LinkedIn/Threads code and `scripts/post.py`.
**Why it's wrong:** It slows every CLI startup, makes a broken platform module capable of breaking unrelated commands, and hides dependency direction.
**Do this instead:** Keep `adapters/__init__.py` limited to `adapters.base` exports, or use module-level `__getattr__` for lazy adapter exports; continue importing concrete adapters inside `get_active_adapters` (`scripts/settings.py:295-318`).

### Duplicated import bootstrap in every script

**What happens:** Each CLI repeats `sys.path.insert` for the repo root and `scripts/`, plus a dual `try/except ImportError` import block (`scripts/pipeline.py:20-35`, `scripts/due.py:30-40`, `scripts/autoposter.py:23-37`, `scripts/ledger.py:20-25`).
**Why it's wrong:** Import behavior differs depending on the current working directory and launch style, and the repeated blocks are easy to update inconsistently.
**Do this instead:** Add a single bootstrap helper (or rely on `pytest.ini`'s `pythonpath = .` plus a root `__init__.py`/package entry strategy) and import `scripts.*` consistently.

### LinkedIn PDF carousel capability is not wired into the automated draft

**What happens:** `repurpose_topic` imports `create_carousel_pdf` (`scripts/repurpose.py:19`) but never calls it, always sets `media_type: "image"` (`scripts/repurpose.py:193-213`), and generates PNG cards instead (`scripts/repurpose.py:155-166`). `create_carousel_pdf` is exercised only by `python -m render.carousel` and tests.
**Why it's wrong:** `LinkedInAdapter.capabilities` advertises `supports_pdf_carousel=True` (`adapters/linkedin.py:213`) and `_async_publish` supports PDF documents (`adapters/linkedin.py:548-557`), but the daily pipeline never produces that payload, so the documented 4-slide PDF carousel is not part of the primary path.
**Do this instead:** Either generate a PDF in `repurpose_topic` for LinkedIn and set `media_type: "carousel"`, or remove the unused import/capability claim until the renderer is integrated.

### Broad exception swallowing hides root causes

**What happens:** Adapters and analytics return failure objects on any exception (`adapters/x.py:89-94`, `adapters/linkedin.py:655-660`, `adapters/threads.py:415-421`, `adapters/bluesky.py:313-318`, `scripts/analytics.py:60-62`) while `capture_failure_artifacts` is only used on selected LinkedIn/Threads failures (`adapters/base.py:43`).
**Why it's wrong:** Session expiry, selector drift, and network errors collapse into the same `success=False` string; operators lose the stack context needed to distinguish them.
**Do this instead:** Keep the normalized `PublishResult`, but attach a failure category and artifact paths to `raw_response`, and log the exception type/message to stderr at the adapter boundary.

## Error Handling

**Strategy:** Fail closed on safety rules, isolate failures per platform, and persist whatever succeeded.

**Patterns:**
- Guardrail exception hierarchy (`GuardRailError`, `CharacterLimitNotMeasuredError`, `EngagementBaitError`, `FabricatedClaimError`, `DuplicatePostError`, `HandleMismatchError`, `AccountWarmupError`) in `scripts/validator.py:288-318`; `validate_draft_guardrails` supports `raise_on_error` for strict publish paths and `(False, errors)` for the due gate (`scripts/validator.py:534-621`).
- Pre-publish guardrails in the X path (`scripts/post.py:445-453`) and in the due gate (`scripts/due.py:174-183`).
- Per-platform try/except in `autoposter` records a failure and continues to the next adapter (`scripts/autoposter.py:185-204`).
- Adapter contracts convert exceptions into `PublishResult(success=False, ...)` rather than crashing the run (`adapters/x.py:89`, `adapters/linkedin.py:655`, `adapters/threads.py:416`).
- Corrupt ledger recovery: parse failure warns and returns a clean v2 state (`scripts/ledger.py:99-110`).
- Operator-actionable failures use `SystemExit(json.dumps({...}))` with a `fix` hint (for example `scripts/post.py:459-464`).
- Stale slots are retired and annotated instead of publishing late (`scripts/due.py:167-171`).
- Failure artifacts (viewport screenshot + DOM dump) are written to `shots/` (`adapters/base.py:43-64`).
- Publication failures and session-expiry signals are dispatched to configured webhooks (`scripts/notify.py:71-93`, `scripts/notify_webhook.py:215-300`).

## Cross-Cutting Concerns

**Logging:** No `logging` module. Scripts print `[TAG]` prefixed lines to stdout and warnings to stderr (for example `scripts/pipeline.py:70`, `scripts/autoposter.py:138`, `scripts/browser.py:264`). Persisted evidence lives in `state.json`, `shots/`, and `drafts/`.

**Validation:** Two distinct systems. Onboarding/live probes in `scripts/validator.py:48-286` verify Bluesky credentials, LLM keys/model IDs, and webhooks with zero external SDKs. Runtime guardrails in `scripts/validator.py:534-621` enforce measured limits, no engagement bait, no duplicates, source traceability, and optional account warm-up.

**Authentication:** X/LinkedIn/Threads rely on cookies in a dedicated browser profile (`scripts/settings.py:126-156`, `scripts/browser.py:88-101`), never on platform APIs. Bluesky uses ATProto app-password sessions (`adapters/bluesky.py:175-195`), resolved from environment or `config.json` (`scripts/settings.py:300-306`). LLM keys and webhook tokens are resolved from environment or the root `.env` (existence noted, contents not read) by `scripts/llm.py:51-84` and `scripts/notify_webhook.py:23-73`.

**Configuration:** `config.json` is merged over `DEFAULTS` recursively (`scripts/settings.py:85-110`); `config.example.json` is the documented template. Browser discovery is platform-aware (`scripts/settings.py:159-195`). A legacy profile migration path keeps `~/.tweetytweets/edge-profile` working (`scripts/settings.py:133-151`).

**Observability:** Docker health uses `python scripts/doctor.py --healthcheck` (`docker-compose.yml:20-25`). `state.json` doubles as the audit log. `scripts/analytics.py` enriches it with engagement metrics, and `scripts/feedback.py` turns those metrics into voice-profile guidance.

---

*Architecture analysis: 2026-10-20*
