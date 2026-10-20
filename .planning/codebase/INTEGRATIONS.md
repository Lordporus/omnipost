# External Integrations

**Analysis Date:** 2026-10-20

## APIs & External Services

**Publishing Platforms:**
- X (Twitter) - No X API or developer account. Publishing is driven through the authenticated browser composer at `https://x.com/compose/post` using CDP (`Input.insertText`, `Page.captureScreenshot`) and verified by reading the profile back.
  - SDK/Client: custom CDP client `scripts/browser.py` + `scripts/post.py`, wrapped by `adapters/x.py`
  - Auth: browser session cookies in the dedicated automation profile (no token env var)
- Bluesky - Native AT Protocol XRPC over HTTPS with zero third-party SDK.
  - SDK/Client: `adapters/bluesky.py` (`urllib`): `https://bsky.social/xrpc/com.atproto.server.createSession`, `com.atproto.repo.uploadBlob`, `com.atproto.repo.createRecord`; public read `https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread` in `scripts/analytics.py`
  - Auth: `BSKY_IDENTIFIER` + `BSKY_APP_PASSWORD` (or `platforms.bluesky.app_password_env` / `platforms.bluesky.app_password` in `config.json`)
- LinkedIn - No LinkedIn API. CDP automation of `https://www.linkedin.com/feed/` with ProseMirror `contenteditable` input injection, stealth script masking `navigator.webdriver`, and a configurable minimum gap (`platforms.linkedin.min_gap_hours`, default 4).
  - SDK/Client: `adapters/linkedin.py` + `scripts/browser.py`
  - Auth: browser session cookies in the automation profile
- Meta Threads - No Meta developer API. CDP automation of `https://www.threads.net/` / `https://www.threads.com/` with native local image attachment.
  - SDK/Client: `adapters/threads.py` + `scripts/browser.py`
  - Auth: browser session cookies in the automation profile

**Content Research:**
- Hacker News (Algolia API) - Story harvesting with no key: `https://hn.algolia.com/api/v1/search_by_date` in `scripts/research.py`
- RSS/Atom feeds - Configured URLs in `config.json` → `feeds`, parsed with `xml.etree.ElementTree` in `scripts/research.py`. Defaults include TechCrunch AI, The Verge AI, HNRSS, arXiv cs.AI, and Simon Willison (`config.example.json`, `scripts/settings.py`)
- Reddit - DOM scrape of `https://www.reddit.com/r/{subreddit}/top/?t=day` through the automation browser because Reddit blocks its `.json` API (`scripts/research.py`)
- X search - DOM scrape of `https://x.com/search?q=...` using the logged-in automation profile (`scripts/research.py`)

**LLM Providers:**
- Google Gemini - `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with `responseMimeType: application/json`; default model `gemini-2.5-flash`
  - SDK/Client: stdlib `urllib.request` in `scripts/llm.py`
  - Auth: `GEMINI_API_KEY`; model override `GEMINI_MODEL`
- OpenAI - `https://api.openai.com/v1/chat/completions` with `response_format: json_object`; default model `gpt-4o-mini`
  - SDK/Client: `scripts/llm.py`
  - Auth: `OPENAI_API_KEY`; model override `OPENAI_MODEL`
- Anthropic Claude - `https://api.anthropic.com/v1/messages` with `anthropic-version: 2023-06-01`; default model `claude-3-5-sonnet-20241022`
  - SDK/Client: `scripts/llm.py`
  - Auth: `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY`; model override `ANTHROPIC_MODEL`
- OpenRouter - `https://openrouter.ai/api/v1/chat/completions`; default model `meta-llama/llama-3.3-70b-instruct`
  - SDK/Client: `scripts/llm.py`
  - Auth: `OPENROUTER_API_KEY`; model override `OPENROUTER_MODEL`
- Provider selection: explicit argument > `LLM_PROVIDER` env var > `config.json` → `llm.provider` > inferred from present keys > `local` (deterministic heuristic fallback in `scripts/generate.py`).
- Key/model pre-flight probes: `https://generativelanguage.googleapis.com/v1beta/models`, `https://api.openai.com/v1/models`, `https://api.anthropic.com/v1/models`, `https://openrouter.ai/api/v1/auth/key`, `https://openrouter.ai/api/v1/models` in `scripts/validator.py`.

**Engagement Metrics:**
- Bluesky public AppView - `app.bsky.feed.getPostThread` for likes/reposts/replies (`scripts/analytics.py`)
- X public syndication - `https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=x` for favorite/retweet/reply/view counts (`scripts/analytics.py`)
- LinkedIn and Threads metrics - declared in the analytics docstring but not implemented; `collect_metrics` only fetches Bluesky and X (`scripts/analytics.py`)

**Notifications:**
- Telegram Bot API - `https://api.telegram.org/bot{token}/sendMessage`, plain-text message plus metadata bullets (`scripts/notify_webhook.py`)
  - Auth: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Discord Webhooks - rich embed payload to `DISCORD_WEBHOOK_URL` with event-colored embeds (`scripts/notify_webhook.py`)
  - Auth: `DISCORD_WEBHOOK_URL`
- Windows desktop toasts - PowerShell `Windows.UI.Notifications` call from `scripts/notify.py` (local only, no third-party service)
- Optional proxy support for webhook calls: `HTTPS_PROXY`/`HTTP_PROXY` or `notifications.proxy` / `webhook_proxy` in `config.json` (`scripts/notify_webhook.py`)

**Connectivity Checks:**
- `https://www.google.com/generate_204` probe in `scripts/publish_now.py`
- Hacker News reachability probe in `scripts/doctor.py`

## Data Storage

**Databases:**
- None. No SQL/NoSQL driver, ORM, or migration tool is present.

**File Storage:**
- Local filesystem only, rooted at the repository (`scripts/settings.py`):
  - `state.json` - unified publishing ledger, schema v2.0, atomic PID-tagged temp-file replacement (`scripts/ledger.py`)
  - `drafts/YYYY-MM-DD.json` - jittered slot plans and per-platform draft payloads
  - `swipe/YYYY-MM-DD.json` - harvested research items (`scripts/research.py`)
  - `.tick` - monotonic tick counter for cron wake/retry (`scripts/due.py`, `scripts/gate.py`)
  - `shots/` - failure screenshots and DOM dumps (`adapters/base.py`)
  - `scratch/cards/`, `scratch/carousels/`, `scratch/infocards/` - generated visual assets
  - `references/voice-profile.local.md` - measured/curated voice profile (git-ignored)
- Browser session persistence: dedicated Chrome/Edge profile directory, default `~/.omnipost/edge-profile` with legacy `~/.tweetytweets/edge-profile`, or `browser.profile_dir` (`scripts/settings.py`, `scripts/browser_daemon.py`).
- Docker: named volume `omnipost_browser_data` mounted at `/app/browser-data` (`docker-compose.yml`).

**Caching:**
- None (no Redis/Memcached). Feed caching is handled implicitly by `state.json`, draft files, and browser profile state.

## Authentication & Identity

**Auth Provider:**
- None (no Auth0, Clerk, Supabase, Firebase, or custom login service).
- Authentication is delegated to each platform's own logged-in browser session stored in the automation profile (X, LinkedIn, Threads), plus an ATProto app password for Bluesky.
- LLM and notification services use bearer/API-key auth read from `.env` or process environment.
- Session health checks: `check_session()` on each adapter and `send_session_expired_alert()` in `scripts/notify_webhook.py` emit a critical webhook when a platform session expires.

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, New Relic, or OpenTelemetry).
- Failure evidence is captured locally: `shots/{platform}_fail.png` and `shots/{platform}_fail.html` via `capture_failure_artifacts` in `adapters/base.py`.

**Logs:**
- Standard output/standard error with bracketed prefixes (`[PIPELINE]`, `[DAEMON]`, `[NOTIFY]`, `[ALERT]`, `[WARN] [ANALYTICS]`).
- systemd captures stdout/stderr to the journal (`systemd/omnipost.service`).
- Docker logs via `docker compose logs -f`; health status via `python scripts/doctor.py --healthcheck` (`docker-compose.yml`).
- Remote alerting through Telegram/Discord on publish success, partial failure, failure, summary cards, and session expiry (`scripts/notify.py`, `scripts/notify_webhook.py`).

## CI/CD & Deployment

**Hosting:**
- Self-hosted: local workstation, Docker host, or a Debian/Ubuntu VPS under `/opt/omnipost` (`scripts/deploy_vps.sh`, `systemd/omnipost.service`).

**CI Pipeline:**
- GitHub Actions `CI` workflow (`.github/workflows/ci.yml`): push/PR to `main`; matrix `ubuntu-latest` + `windows-latest` × Python `3.10`, `3.11`, `3.12`; installs `requirements.txt`; runs `pytest -v` with `CI=true`, `HEADLESS=1`, and empty notification credentials.
- No image publishing, release automation, or deployment job in CI.

## Environment Configuration

**Required env vars:**
- LLM: `LLM_PROVIDER`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_MODEL`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `OPENROUTER_MODEL`
- Bluesky: `BSKY_IDENTIFIER`, `BSKY_APP_PASSWORD` (configurable via `platforms.bluesky.app_password_env`)
- Notifications: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL`
- Networking: `HTTPS_PROXY`, `HTTP_PROXY` (and lowercase variants)
- Runtime/deployment: `DISPLAY`, `HEADLESS`, `IS_DOCKER`, `IS_LINUX`, `BROWSER_PROFILE`, `CHROME_PATH`, `TZ` / `TIMEZONE`, `DRY_RUN`
- Onboarding hints: `X_HANDLE`, `LINKEDIN_PROFILE_URL`, `THREADS_HANDLE` (`scripts/wizard.py`)

**Secrets location:**
- `.env` in the repository root (present in this workspace; git-ignored). Contents were not read.
- `config.json` in the repository root (present in this workspace; git-ignored). It can hold `platforms.bluesky.app_password`; contents were not read.
- `.env` is written by the onboarding wizard (`scripts/wizard.py:_write_env_file`) and loaded by `scripts/llm.py` and `scripts/notify_webhook.py` as an `os.environ` fallback.
- Browser cookies/passwords live in the automation browser profile directory, which is git-ignored (`.gitignore`).

## Webhooks & Callbacks

**Incoming:**
- None. There is no HTTP server, route, or inbound webhook handler.

**Outgoing:**
- Telegram Bot `sendMessage` and Discord webhook embeds for publish events and session-expiry alerts (`scripts/notify_webhook.py`, `scripts/notify.py`).
- Optional rich executive summary card per publishing run (`dispatch_summary_card` in `scripts/notify_webhook.py`).

## Integration Notes

- Dual browser-port defaults exist: `9222` in `config.example.json` and `scripts/settings.py`, versus `9444` in `scripts/browser_daemon.py`, `adapters/x.py`, and `launch_edge.bat`. The effective port is the `browser.port` value in `config.json`.
- All outbound HTTP for publishing, research, LLM, validation, and notifications uses the Python standard library (`urllib.request`); `requests` is declared but unused.
- No API keys are required for X, LinkedIn, Threads, Hacker News, RSS, Bluesky reads, or X metrics; only Bluesky publishing, LLM synthesis, and webhook alerts need credentials.

---

*Integration audit: 2026-10-20*
