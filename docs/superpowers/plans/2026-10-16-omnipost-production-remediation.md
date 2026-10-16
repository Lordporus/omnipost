# OmniPost V2.0: Brainstormed Validation & Phased Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform OmniPost V2.0 from a prototype with missing LLM plumbing and hardcoded host paths into an enterprise-grade, zero-cost, sovereign cross-platform publishing engine ready for both unattended personal deployment and public open-source distribution.

**Architecture:** 
1. Hermetic runtime environment with dynamic root path resolution and fully isolated unit testing.
2. Lightweight multi-provider LLM synthesis engine (`scripts/llm.py`) using zero external SDK dependencies (Python `urllib` standard library) that transforms raw RSS/HN intelligence into structured, voice-aligned drafts with modern defaults (`gemini-2.5-flash`), configurable model env vars, strict 15s timeouts, and guaranteed heuristic fallback.
3. Unified browser automation profile with legacy migration: seamlessly detects and preserves existing logged-in sessions in `~/.tweetytweets/edge-profile` before migrating/falling back to `~/.omnipost/edge-profile`.
4. Hardened credential validation loops in `setup.py` and timeout-resilient webhook dispatching.
5. GitHub Actions CI workflow verifying the entire 184+ test matrix on both Windows and Linux runners with hermetic mock environment variables.

**Tech Stack:** Python 3.10–3.12, Chrome DevTools Protocol (CDP over WebSockets), ATProto XRPC (Bluesky), Pillow, Headless Chromium / Edge (`Page.printToPDF`), pytest.

**Spec:** [`AUDIT_AND_GAP_ANALYSIS.md`](file:///c:/Users/Sachin/Downloads/TEST-TWEETYTWEET/AUDIT_AND_GAP_ANALYSIS.md)

---

## Part 1: Brainstorming & Customer Pain-Point Validation

Before locking the implementation tasks, we challenged the architecture against real customer needs, operator realities, and pre-flight blind spots:

### 1. Customer Value Proposition vs. Current Architecture
| Customer Need / Pain Point | Prototype Reality | The Architectural Fix |
| :--- | :--- | :--- |
| **"The posts sound like a real person, not an RSS bot."** | Currently just truncates RSS titles: `title[:90]` + `summary[:300]`. No LLM is ever called. | Implement `scripts/llm.py` calling Gemini/Claude/OpenAI with modern defaults (`gemini-2.5-flash`) and calibrated voice rules from `voice-profile.local.md`. |
| **"I ran setup and logged into Edge, why does it say Not Logged In?"** | `launch_edge.bat` used `.omnipost`, but `browser_daemon.py` hardcoded `C:\Users\Sachin\.tweetytweets`. | Implement legacy detection: if `~/.tweetytweets/edge-profile` exists, preserve it; otherwise use `~/.omnipost/edge-profile`. |
| **"I cloned the repo, why does `pytest` and `doctor.py` crash?"** | Missing `pytest.ini` and missing root `sys.path` injection in `scripts/settings.py`. | Inject root path into `sys.path` dynamically and supply `pytest.ini`. |
| **"My Telegram notifications hang for 60 seconds."** | Indian ISPs throttle `api.telegram.org` SSL handshakes; no timeout ceiling or proxy. | Add 5s timeout, proxy support, and fail-safe fallback to Discord webhooks. |
| **"I mistyped my Bluesky password during onboarding and it silently failed forever."** | Wizard logged a warning but saved the bad password and set `enabled: true`. | Re-prompt loop on failed credential validation; disable channel if user skips. |
| **"Does my account get banned on day 1?"** | Risk of aggressive posting on fresh accounts. | Enforce warmup pacing (1 post/day for 14 days) and `gate.py` schedule jitter. |

---

## Part 2: Global Constraints & Review Focus

### Global Constraints
* **Zero API Cost Core:** Upstream browser automation (X, LinkedIn, Threads) and Bluesky XRPC must remain 100% free of SaaS subscriptions.
* **Zero Bloat:** LLM client in `scripts/llm.py` must use Python standard library (`urllib.request`) without requiring bulky SDKs (`google-generativeai`, `openai`, `anthropic`).
* **Cross-Platform Portability:** Zero hardcoded `C:\Users\Sachin` strings; all paths must resolve dynamically via `Path.home()` or repo `ROOT`.
* **Atomic State Safety:** Every write to `state.json` must be atomic (temp file write + replace).

### Review Focus
1. **LLM Schema Enforcement & Resilience:** LLM responses must strictly parse into JSON (`headline`, `body`, `points`, `takeaway`, `category`). Calls must have explicit `timeout=15.0`, `User-Agent: OmniPost-Synthesizer/2.0`, and catch `urllib.error.URLError`, `urllib.error.HTTPError`, `json.JSONDecodeError`, and `TimeoutError` to guarantee heuristic fallback.
2. **Session Preservation (Zero Orphaned Logins):** Active logins in `~/.tweetytweets/edge-profile` must be automatically detected, reported, and preserved rather than wiped or orphaned by a naive switch to `~/.omnipost/edge-profile`.
3. **Test Hermeticity & CI Mocking:** Running tests locally or in GitHub Actions must NEVER read from real `.env` or trigger unmocked live network calls. CI runners must inject dummy mock environment variables (`CI=true`, `HEADLESS=1`, mock keys).
4. **Edge Session Detection:** Browser daemon must detect when Edge is already running on port 9444 and avoid spawning orphan instances.
5. **Threads Base Domain:** Navigation must strictly target `https://www.threads.net/`.
6. **Byte-Facet Calculations:** Bluesky facet indices must always be UTF-8 byte offsets, never Python string character slices.

---

## Part 3: Phased Implementation Plan

### Task 1: Environment, Import Hierarchy & Test Hermeticity

**Files:**
* Create: `pytest.ini`
* Modify: `scripts/settings.py:10-35`
* Modify: `tests/test_notify_webhook.py:50-80`
* Modify: `requirements.txt:1-15`

**Interfaces:**
* Consumes: System `PYTHONPATH`, local file environment.
* Produces: Clean imports of `adapters.*` and `render.*` from any script working directory; 100% isolated unit tests.

- [x] **Step 1: Write root `pytest.ini`**
  Configure `pythonpath = .` and `testpaths = tests` so running `pytest` works out of the box.

- [x] **Step 2: Add dynamic ROOT path resolution to `scripts/settings.py`**
  ```python
  ROOT = Path(__file__).resolve().parent.parent
  if str(ROOT) not in sys.path:
      sys.path.insert(0, str(ROOT))
  ```

- [x] **Step 3: Fix test isolation in `tests/test_notify_webhook.py`**
  Mock `_read_env_fallback()` in `test_discord_webhook_dispatch` so on-disk `.env` tokens do not trigger unintended Telegram dispatches during Discord tests.

- [x] **Step 4: Update `requirements.txt`**
  Include `requests>=2.28.0` and add `pytest>=8.0.0` under developer dependencies.

- [x] **Step 5: Verify all tests pass**
  Run: `pytest`
  Expected: **184 passed, 0 failed** (Verified: 185 passed, 0 failed).

---

### Task 2: Browser Profile Unification, Session Preservation & Threads Domain Correction

**Files:**
* Modify: `scripts/browser_daemon.py:35-55`
* Modify: `scripts/settings.py:120-130`
* Modify: `launch_edge.bat:1-5`
* Modify: `adapters/threads.py:35-50`
* Test: `tests/test_browser_daemon.py`
* Test: `tests/test_threads.py`

**Interfaces:**
* Consumes: `settings.get_browser_config()`, host filesystem.
* Produces: Dynamic browser data directory at `~/.omnipost/edge-profile` with automatic preservation of existing `~/.tweetytweets/edge-profile`; validated `threads.net` navigation.

- [x] **Step 1: Implement legacy profile detection and fallback in `scripts/browser_daemon.py` and `scripts/settings.py`**
  Replace hardcoded `C:\Users\Sachin\.tweetytweets\...` with dynamic resolution:
  ```python
  legacy_profile = Path.home() / ".tweetytweets" / "edge-profile"
  default_profile = Path.home() / ".omnipost" / "edge-profile"

  # If legacy profile exists with cookies and new profile does not, preserve legacy
  if legacy_profile.exists() and not default_profile.exists():
      profile_path = str(legacy_profile)
  else:
      profile_path = str(default_profile)

  profile = cfg.get("profile_dir") or profile_path
  ```

- [x] **Step 2: Update `launch_edge.bat` with matching precedence**
  Check if `%USERPROFILE%\.tweetytweets\edge-profile` exists; if so, open it to preserve existing user logins, otherwise open `%USERPROFILE%\.omnipost\edge-profile`.

- [x] **Step 3: Correct Meta Threads base URL**
  In `adapters/threads.py:39`, set `THREADS_BASE_URL = "https://www.threads.net/"`.

- [x] **Step 4: Run test suite**
  Run: `pytest tests/test_browser_daemon.py tests/test_threads.py`
  Expected: All tests pass (Verified: 16 passed, 0 failed).

---

### Task 3: Real LLM Content Synthesis Engine with Modern Defaults (`scripts/llm.py` & `scripts/generate.py`)

**Files:**
* Create: `scripts/llm.py`
* Modify: `scripts/generate.py:1-78`
* Modify: `scripts/repurpose.py:75-110`
* Create: `tests/test_llm.py`

**Interfaces:**
* Consumes: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` + model overrides (`GEMINI_MODEL`, `OPENAI_MODEL`, etc.) from `.env` or `config.json`; voice profile markdown.
* Produces: `generate_topic_with_llm(items, kind, voice_profile) -> dict` returning validated JSON `{headline, body, points, takeaway, category}` with robust error handling and zero-cost heuristic fallback.

- [x] **Step 1: Write failing test for LLM provider in `tests/test_llm.py`**
  Test Gemini (`gemini-2.5-flash`), OpenAI (`gpt-4o-mini`), Claude (`claude-3-5-sonnet`), configurable model env overrides (`GEMINI_MODEL`), explicit timeouts, and fallback on network/JSON errors with mocked HTTP endpoints.

- [x] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_llm.py`
  Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.llm'`.

- [x] **Step 3: Implement `scripts/llm.py` with resilience & modern defaults**
  Lightweight client using standard library `urllib.request`:
  * **Modern Defaults:**
    * Gemini: `gemini-2.5-flash` (override via `os.environ.get("GEMINI_MODEL") or cfg.get("model")`)
    * OpenAI: `gpt-4o-mini` (override via `os.environ.get("OPENAI_MODEL") or cfg.get("model")`)
    * Claude: `claude-3-5-sonnet-20241022` (override via `os.environ.get("ANTHROPIC_MODEL") or cfg.get("model")`)
    * OpenRouter: `meta-llama/llama-3.3-70b-instruct` (override via `os.environ.get("OPENROUTER_MODEL") or cfg.get("model")`)
  * **Strict Request Hygiene:**
    * Explicit `timeout=15.0`.
    * Standard header `User-Agent: OmniPost-Synthesizer/2.0`.
    * Clean exception handling catching `(urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError, KeyError)` returning `(False, fallback_dict)`.

- [x] **Step 4: Connect `scripts/generate.py` to `scripts/llm.py`**
  Update `generate_topic_from_items` to load provider and key from settings/`.env`, pass voice profile instructions, and return rich polymorphic topics with automatic fallback.

- [x] **Step 5: Run tests to verify they pass**
  Run: `pytest tests/test_llm.py tests/test_generate.py`
  Expected: PASS (Verified: 20 passed, 0 failed).

---

### Task 4: Wizard Credential Re-Prompting & Webhook Network Resilience

**Files:**
* Modify: `scripts/wizard.py:235-305`
* Modify: `scripts/notify_webhook.py:70-120`
* Test: `tests/test_wizard.py`
* Test: `tests/test_notify_webhook.py`

**Interfaces:**
* Consumes: Operator keyboard input during onboarding; webhook URLs and tokens.
* Produces: Validated `.env` file without silent credential corruption; non-blocking webhook dispatches.

- [x] **Step 1: Add re-prompt loop in `scripts/wizard.py`**
  If `validate_bluesky_credentials` or `validate_llm_key` fails:
  * Print specific failure reason (e.g. `Bluesky authentication failed: Invalid identifier or password`).
  * Re-prompt operator: `Re-enter credentials? [Y/n]`.
  * If skipped, set `platforms[platform]["enabled"] = False` and warn operator.

- [x] **Step 2: Implement strict timeout and proxy support in `scripts/notify_webhook.py`**
  Set `DEFAULT_TIMEOUT = 5.0` and allow configuring HTTP/HTTPS proxy from `config.json` for Telegram requests.

- [x] **Step 3: Run wizard and webhook unit tests**
  Run: `pytest tests/test_wizard.py tests/test_notify_webhook.py`
  Expected: All tests pass (Verified: 25 passed, 0 failed; full suite 214 passed).

---

### Task 5: Hermetic GitHub Actions CI/CD & Open Source Packaging

**Files:**
* Create: `.github/workflows/ci.yml`
* Create: `CONTRIBUTING.md`
* Create: `SECURITY.md`
* Modify: `config.json` (Sanitize host-specific paths)
* Modify: `state.json` (Sanitize local Windows paths)

**Interfaces:**
* Consumes: Git commits and pull requests.
* Produces: Automated cross-platform CI verification on GitHub.

- [ ] **Step 1: Create `.github/workflows/ci.yml` with hermetic test environment**
  Matrix test runner testing Python 3.10, 3.11, and 3.12 on both `ubuntu-latest` and `windows-latest`.
  Supply explicit mock environment variables:
  ```yaml
  env:
    CI: "true"
    HEADLESS: "1"
    GEMINI_API_KEY: "mock-gemini-key"
    OPENAI_API_KEY: "mock-openai-key"
    ANTHROPIC_API_KEY: "mock-anthropic-key"
    BSKY_IDENTIFIER: "mock.bsky.social"
    BSKY_APP_PASSWORD: "mock-app-password"
    TELEGRAM_BOT_TOKEN: ""
    TELEGRAM_CHAT_ID: ""
    DISCORD_WEBHOOK_URL: ""
  ```

- [ ] **Step 2: Sanitize local paths in `config.json` and `state.json`**
  Replace absolute `C:\Users\Sachin\...` paths with relative or portable home paths.

- [ ] **Step 3: Add `CONTRIBUTING.md` and `SECURITY.md`**
  Provide clear contribution guidelines and security disclosure instructions.

- [ ] **Step 4: Run end-to-end dry-run and live tests**
  Run: `python scripts/prereq_check.py` and `python scripts/doctor.py`
  Expected: All checks green.
