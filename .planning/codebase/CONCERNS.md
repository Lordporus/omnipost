<!-- refreshed: 2026-10-20 -->
# Codebase Concerns

**Analysis Date:** 2026-10-20

Scope: full repository at `C:/Users/Sachin/Downloads/TEST-TWEETYTWEET`, no path filter. Findings are
grounded in current source, not in `AUDIT_AND_GAP_ANALYSIS.md` (which is stale in several places).
Method note: 230 test functions were counted statically, but the suite was **not executed** in this
environment (`pytest` is not installed in the available Python interpreters). No pass/fail claim is made.

## Tech Debt

**Split-brain ledger with two incompatible writers:**
- Issue: `scripts/ledger.py` implements atomic Schema v2 writes (`os.replace` via temp file), but
  `scripts/post.py:72-79` keeps a second, non-atomic `load_state`/`save_state` pair writing the same
  `state.json` without migration or locking.
- Files: `scripts/ledger.py`, `scripts/post.py`
- Impact: `post.py` can persist a legacy-shaped record that `ledger.migrate_state` must repair later;
  a crash mid-write truncates `state.json`; the two modules can disagree on schema.
- Fix approach: delete `post.py`'s local ledger functions and call `ledger.load_state` /
  `ledger.save_state` everywhere. Add one file-lock abstraction (`msvcrt`/`fcntl`) inside `ledger.py`.

**`dry_run` in config is decorative:**
- Issue: the wizard writes `config.json["dry_run"]` (`scripts/wizard.py:553-565`), but no publishing
  path reads it. `scripts/autoposter.py:105` and `scripts/publish_now.py:180` only honor their CLI
  `--dry-run` flag, and `scripts/daemon.py` passes no flag.
- Files: `config.json`, `scripts/autoposter.py`, `scripts/daemon.py`, `scripts/wizard.py`
- Impact: a user who completes onboarding with `dry_run: true` still gets live posts from the daemon.
  The demo safety switch is the single most dangerous gap in the repo.
- Fix approach: resolve an effective dry-run value as `CLI flag OR config["dry_run"]` in one helper
  (`scripts/settings.py`), and consume it in `autoposter`, `publish_now`, and `daemon`.

**`due()` drops the platform-native payload:**
- Issue: plans store per-platform copy under `slot["platforms"]` (`scripts/pipeline.py:58-60`), but
  `due()` returns only `date/slot/kind/due_at/text/image/minutes_late`
  (`scripts/due.py:192-195`).
- Files: `scripts/due.py`, `scripts/autoposter.py`, `scripts/pipeline.py`
- Impact: `autoposter` reads `due_item.get("platforms", {})` (always `{}`), so `adapted_text`
  falls back to the X text on Bluesky, LinkedIn, and Threads. Platform-native repurposing is
  effectively dead in the autonomous path.
- Fix approach: include `platforms` and `headline` in the `due()` payload and add a contract test
  asserting the returned dict matches what `autoposter` consumes.

**Swipe file schema drift (dict vs list):**
- Issue: `scripts/research.py:366-371` writes `{"counts": ..., "items": [...]}`, while
  `scripts/generate.py:430-436` returns `json.loads(...)` directly and is typed/used as a list.
  `scripts/pipeline.py:47` then slices it (`swipe_items[idx * 3:(idx + 1) * 3]`).
- Files: `scripts/research.py`, `scripts/generate.py`, `scripts/pipeline.py`
- Impact: once `swipe/<date>.json` exists, the daily pipeline raises
  `TypeError: unhashable type: 'slice'` and stops generating content. It only works today because
  `swipe/` is empty and the pipeline falls back to `research.hn(...)`.
- Fix approach: make `load_daily_swipe` return `.get("items", [])` with a legacy-list fallback, and
  add a round-trip test that writes with `collect()` and reads with `load_daily_swipe()`.

**Platform limits hardcoded in the repurposer:**
- Issue: `scripts/repurpose.py` hardcodes 280 (X), 300 (Bluesky), and 3000 (LinkedIn) at lines 23-81,
  duplicating `settings.limit()`, `PlatformCapabilities.max_characters`, and measured `config.json`
  ceilings.
- Files: `scripts/repurpose.py`, `scripts/settings.py`, `adapters/*.py`
- Impact: measuring a real ceiling (e.g. Premium X at 25k) changes publishing behavior but not
  repurposing; drafts are silently truncated to the wrong caps.
- Fix approach: derive caps from `settings.limit(cfg, platform)` and adapter capabilities; keep a
  single fallback table in `settings.py`.

**Tautological exception clauses:**
- Issue: `except (CDPError, OSError, asyncio.TimeoutError, Exception)` in
  `adapters/threads.py:268` and `except (..., Exception)` in `scripts/llm.py:526-533` make the
  explicit types meaningless and silence unexpected programming errors.
- Files: `adapters/threads.py`, `scripts/llm.py`
- Impact: real defects (attribute errors, schema errors) are downgraded to "platform failed" log
  lines, hiding root causes.
- Fix approach: remove `Exception` from the tuple and add a final `except Exception` that logs with
  traceback (`logger.exception` or `traceback.format_exc()`).

**Docker packaging contract is broken:**
- Issue: no `.dockerignore`, so `COPY . /app` (`Dockerfile:26`) bakes `.env`, `config.json`,
  `state.json`, `drafts/`, `swipe/`, `.git/`, and any local browser profile into image layers.
  `scripts/docker-entrypoint.sh:14` tells users to copy `.env.example`, which does not exist.
  `BROWSER_PROFILE` and `CHROME_PATH` (`docker-compose.yml:11-12`) are never read by code.
- Files: `Dockerfile`, `docker-compose.yml`, `scripts/docker-entrypoint.sh`, `scripts/settings.py`
- Impact: secret leakage in image layers; the named volume `omnipost_browser_data` is mounted but
  unused, so every container recreate loses all cookies and requires re-login. README's "Persistent
  Sessions" claim (line 220) is false.
- Fix approach: add `.dockerignore` (`.env`, `config.json`, `state.json`, `drafts/`, `swipe/`,
  `shots/`, `scratch/`, `.git/`, profiles), ship a real `.env.example`, and teach
  `settings.profile_dir()` / `find_chrome()` to honor `BROWSER_PROFILE` and `CHROME_PATH`.

**Non-atomic plan writes:**
- Issue: `scripts/due.py:96-97` and `:170`, plus `scripts/pipeline.py:102`, write `drafts/*.json`
  with plain `write_text`.
- Files: `scripts/due.py`, `scripts/pipeline.py`
- Impact: the daemon runs `pipeline.py` and `autoposter.py` as separate processes; a tick during a
  pipeline write can read a truncated plan or lose a just-marked slot.
- Fix approach: reuse an atomic `write_json` helper (temp file + `os.replace`) and take the same
  lock used by the ledger.

**Stale audit and README claims:**
- Issue: `AUDIT_AND_GAP_ANALYSIS.md` still lists fixed items (pytest config, LLM wiring, CI,
  threads.net) as Pending, and README advertises "230 passed" plus persistent Docker sessions
  without a reproducible run.
- Files: `AUDIT_AND_GAP_ANALYSIS.md`, `README.md`
- Impact: future agents and contributors re-fix solved problems and trust guarantees the runtime
  does not provide.
- Fix approach: regenerate the audit from current code and replace static badges with CI-derived
  status.

**Dirty working tree:**
- Issue: 15 tracked files are modified (including `adapters/*`, `scripts/pipeline.py`,
  `scripts/post.py`, `scripts/settings.py`) with untracked phase directories and the new audit doc.
- Files: repository root (`git status`)
- Impact: review boundaries are unclear and the "last known good" commit does not match the analyzed
  behavior.
- Fix approach: commit or stash the hardening work in reviewable slices before further changes.

## Known Bugs

**Autoposter publishes identical X copy to every platform:**
- Symptoms: Bluesky/LinkedIn/Threads receive the X-formatted text, including X-specific hooks and
  length assumptions; platform drafts in `drafts/*.json` are ignored.
- Files: `scripts/due.py:192-195`, `scripts/autoposter.py:117-157`
- Trigger: any plan where `slot["platforms"]` is populated, then run `python scripts/autoposter.py`.
- Workaround: none in the daemon path; only manual `publish_now.py` picks `--platforms` drafts.
- Fix: return `platforms` from `due()` (see Tech Debt).

**Pipeline crashes on a real swipe file:**
- Symptoms: `TypeError: unhashable type: 'slice'` at `scripts/pipeline.py:47`.
- Files: `scripts/pipeline.py:47`, `scripts/generate.py:430-436`, `scripts/research.py:366-371`
- Trigger: run `python scripts/research.py collect`, then `python scripts/pipeline.py`.
- Workaround: delete `swipe/<date>.json` so the fallback path runs.
- Fix: normalize the schema at the loader boundary.

**Bluesky can send the env var *name* as the password:**
- Symptoms: login fails with an invalid identifier/password error, or worse, a literal
  `BSKY_APP_PASSWORD` string is sent as the secret.
- Files: `adapters/bluesky.py:110-118`
- Trigger: config sets `app_password_env` but the variable is unset; the `or (env_var_name if
  env_var_name and not env_pass else "")` fallback returns the variable name.
- Workaround: ensure the env var exists, or put the secret in `app_password`.
- Fix: remove that fallback and raise a clear "credential env var not set" error.

**LinkedIn 4-hour rate limit never fires:**
- Symptoms: back-to-back LinkedIn posts are allowed despite `min_gap_hours: 4`.
- Files: `adapters/linkedin.py:217-232`
- Trigger: two publishes within four hours on Schema v2 state.
- Workaround: none; manual spacing only.
- Fix: read `p["platforms"]["linkedin"]["status"] == "published"` and `p["at"]`, with a migration
  fallback for legacy `outcomes`/`platform` records.

**AI-update header is lost on the adapter path:**
- Symptoms: the X post from the daemon has no `Daily AI updates | Day N` header and
  `ai_update_day` never advances.
- Files: `adapters/x.py:59-71`, `adapters/base.py:20-30`, `scripts/autoposter.py:174-182`
- Trigger: due slot of `kind: "ai_update"` published by `autoposter`.
- Workaround: publish that slot with `post.py post --kind ai_update`.
- Fix: add `kind` to `PublishPayload` (or read `extra_metadata["kind"]` in `XAdapter.publish`) and
  forward it to `post.do_post(kind=...)`.

**Possible duplicate X post from `_click_post`:**
- Symptoms: two identical posts, or a "duplicate content" composer warning after one logical click.
- Files: `scripts/post.py:331-337`
- Trigger: mouse press/release succeeds, then the unconditional JS `b.click()` fires as well.
- Workaround: check the profile timeline and delete the duplicate.
- Fix: dispatch exactly one activation path; only fall back to JS if `btn_disabled` is still true
  after the mouse event, and add a post-click navigation/URL wait before returning.

**`publish_now` timeout does not bound the publish:**
- Symptoms: the process hangs past `--timeout`; the ledger records `network_timeout` even when the
  post later succeeds, so a retry duplicates it.
- Files: `scripts/publish_now.py:243-278`
- Trigger: adapter publish exceeds `--timeout` (default 80s).
- Workaround: inspect the feed manually before retrying; no reconciliation exists.
- Fix: do not use `with ThreadPoolExecutor(...)` (its `__exit__` waits); keep the executor alive,
  record `unknown`, and reconcile with `adapter.verify()` before allowing a retry.

**Corrupt `state.json` can wipe history:**
- Symptoms: `ledger.load_state` prints a warning and returns an empty state; the next save overwrites
  the damaged file, permanently losing all posts and `ai_update_day`.
- Files: `scripts/ledger.py:99-110`, `scripts/post.py:72-75`
- Trigger: truncated/partially written `state.json`, or a manual edit with a JSON error.
- Workaround: restore from backup/git history (state is gitignored, so usually none).
- Fix: on parse failure, rename the bad file to `state.corrupt.<ts>.json`, refuse to save, and fail
  loudly; `post.py` should not raise an unhandled `JSONDecodeError`.

**Guardrail-blocked slots silently stall forever:**
- Symptoms: `due()` returns `None` every tick while a slot sits past due; no notification.
- Files: `scripts/due.py:173-183`
- Trigger: warmup cap, engagement bait, duplicate, or unmeasured ceiling rejects the slot.
- Workaround: run `due.py check` and inspect manually; nothing is persisted.
- Fix: persist `guardrail_blocked` to the plan atomically, mark it `posted: true, skipped: reason`,
  and dispatch a `notify_webhook` warning.

**Generated Threads copy trips the engagement-bait guard:**
- Symptoms: `repurpose.format_threads` appends "What are your thoughts?", which is in
  `ENGAGEMENT_BAIT_PATTERNS` (`scripts/validator.py:323-344`), so autonomous validation rejects a
  draft the pipeline just produced.
- Files: `scripts/repurpose.py:97`, `scripts/validator.py:323-344`
- Trigger: any slot repurposed for Threads, then validated.
- Workaround: manually remove the line.
- Fix: replace with a specific question or drop the CTA; add a cross-module test that every
  repurposer output passes `validate_draft_guardrails`.

**Source-trace guardrail is inert:**
- Symptoms: `require_verified_source` never blocks anything.
- Files: `scripts/validator.py:448-476`, `scripts/validator.py:604`, `scripts/post.py:445-453`,
  `scripts/due.py:174-180`
- Trigger: all current call sites pass drafts without `source_url`; `due.py` never passes
  `swipe_dir`, and `post.py` passes `draft={"text": body}` only.
- Workaround: none.
- Fix: carry `source_url` from research items through `generate`/`repurpose` into the plan, pass
  `swipe_dir` from `due.py`, and make "no source" an explicit policy decision rather than an
  accidental pass.

**Docker "persistent browser sessions" does not persist:**
- Symptoms: after `docker compose up --force-recreate`, all platform sessions are logged out.
- Files: `docker-compose.yml:11-14`, `scripts/settings.py:profile_dir`, `config.json` `browser.profile_dir`
- Trigger: recreate the container with the host `config.json` bind mount, which contains a
  host-specific profile path that overrides the volume.
- Workaround: re-run login in the container.
- Fix: honor `BROWSER_PROFILE` with highest precedence and make the container config path-independent.

## Security Considerations

**Secrets committed to image layers:**
- Risk: `COPY . /app` includes `.env`, `config.json` (inline `app_password` key), `state.json`, and
  browser profiles; anyone with the image can extract live credentials and cookies.
- Files: `Dockerfile:26`, `docker-compose.yml`, `.gitignore`
- Current mitigation: `.gitignore` excludes these files from git only; there is no `.dockerignore`.
- Recommendations: add `.dockerignore`, switch to `docker build --secret`/env-only credentials,
  and rotate any credential that has ever been baked into an image.

**Secrets in URLs and unredacted error output:**
- Risk: the Telegram bot token is interpolated into the request path
  (`scripts/notify_webhook.py:130`), and Gemini keys into the query string
  (`scripts/llm.py:371-372`). Both appear in proxy logs, shell history, and exception text.
  `notify_webhook.py:159-160` prints the raw exception, which can contain the URL.
- Files: `scripts/notify_webhook.py`, `scripts/llm.py`
- Current mitigation: HTTPS transport; `.env` is gitignored.
- Recommendations: move Gemini to the `x-goog-api-key` header, redact tokens before logging
  (`re.sub(r"bot[^/]+", "bot***", ...)`), and send Telegram via POST body.

**`.env` fallback bypasses environment isolation:**
- Risk: `scripts/llm.py:51-68` and `scripts/notify_webhook.py:23-41` parse `.env` even when process
  env is populated, so a stray or stale local file can override operator intent and leak into
  child processes.
- Files: `scripts/llm.py`, `scripts/notify_webhook.py`, `scripts/settings.py`
- Current mitigation: none; the fallback always runs.
- Recommendations: read `.env` only when `IS_DOCKER` is unset and the variable is absent from
  `os.environ`; document precedence in one place.

**Browser profiles contain live session cookies:**
- Risk: profiles under `~/.omnipost`, `~/.tweetytweets`, and the Docker volume are unencrypted and
  world-readable by default; `scripts/launch_desktop_edge.py:48` force-kills Edge processes.
- Files: `scripts/settings.py`, `scripts/browser_daemon.py`, `scripts/launch_desktop_edge.py`
- Current mitigation: `.gitignore` entries and a dedicated profile directory.
- Recommendations: restrict directory permissions (`0o700`), avoid force-killing user Edge
  instances, and document profile backup/rotation.

**Container runs as root:**
- Risk: any RCE through scraped pages or a malicious feed escalates to root inside the container,
  and bind-mounted `state.json`/`drafts` are written as root on the host.
- Files: `Dockerfile`, `docker-compose.yml`
- Current mitigation: no published ports; non-root not configured.
- Recommendations: add a `USER omnipost` after setup, `chown` the volume, and drop capabilities.

**Notification toggles are ignored:**
- Risk: `config.json["notifications"]` settings are not consulted by `scripts/notify.py` /
  `notify_webhook.py`, so disabling alerts does not stop outbound calls containing post text.
- Files: `config.json`, `scripts/notify.py`, `scripts/notify_webhook.py`
- Current mitigation: alert failures are swallowed.
- Recommendations: gate every dispatch on the config toggles and add a redaction test.

## Performance Bottlenecks

**Sequential browser scraping dominates pipeline time:**
- Problem: `research.reddit` and `research.x` call `browser.scrape_many(..., settle=6/7)` over a
  list of URLs; each URL waits the full settle plus polling up to 40s
  (`scripts/browser.py:217-227,245-286`). `daemon.py` blocks on `subprocess.run` with no timeout.
- Files: `scripts/research.py:204,266`, `scripts/browser.py`, `scripts/daemon.py:41`
- Cause: one CDP tab per URL, fixed sleeps instead of network-idle/selector waits.
- Improvement path: reuse one tab, wait on a selector with a bounded timeout, add
  `subprocess.run(..., timeout=...)`, and cap total collection time.

**Per-tick revalidation and repeated JSON parsing:**
- Problem: every 5-minute tick, `due()` parses all plans, recomputes `_posted_slots` per plan, runs
  guardrails per candidate (including globbing every `swipe/*.json` for source traces), and re-reads
  the winning plan.
- Files: `scripts/due.py:101-195`, `scripts/validator.py:448-476`
- Cause: no caching or indexes; linear scans over growing directories.
- Improvement path: index plans by date, cache swipe URLs per tick, and short-circuit the trace
  check when `require_verified_source` is false.

**Unbounded flat-file growth:**
- Problem: `state.json` holds every post forever (25 now) and is fully rewritten per status update;
  `_load_plans` globs all files then filters by date only after reading.
- Files: `scripts/ledger.py:113-121`, `scripts/due.py:101-115`
- Cause: no retention policy or date-indexed storage.
- Improvement path: archive posts older than N days into monthly files and filter plan filenames
  before opening them.

**Image rendering in the critical path:**
- Problem: `repurpose`/`render/carousel.py` generate Pillow images inline for every slot before the
  plan is saved; failures or large fonts extend the 11:00 pipeline run.
- Files: `scripts/repurpose.py`, `render/carousel.py`, `scripts/pipeline.py`
- Cause: synchronous CPU work with no budget or fallback limit.
- Improvement path: render lazily at publish time, cache by content hash, and add a per-slot
  timeout with a text-only fallback.

**Blocking publishes serialize all platforms:**
- Problem: `autoposter` loops adapters serially; each CDP post can take tens of seconds, so one
  slow LinkedIn upload delays X/Bluesky/Threads and exceeds the 5-minute cadence.
- Files: `scripts/autoposter.py:132-204`, `scripts/publish_now.py`
- Cause: synchronous adapter interface over one browser port.
- Improvement path: bounded parallel dispatch (one worker per platform, separate ports/tabs) and
  persist per-platform progress between ticks.

## Fragile Areas

**DOM-selector automation:**
- Files: `adapters/x.py`, `adapters/linkedin.py`, `adapters/threads.py`, `scripts/post.py`,
  `scripts/browser.py`
- Why fragile: hardcoded `data-testid`/`aria-label` selectors, fixed sleeps, and toast/readback
  verification; upstream A/B tests break publishing instantly. `launch_desktop_edge.py:48` also
  kills any `msedge.exe` whose command line matches `9444` or `tweetytweets`.
- Safe modification: add selectors in one constants block, keep a text-snippet fallback, and always
  capture `shots/<platform>_fail.png` + HTML.
- Test coverage: all CDP calls are mocked; no live smoke test in CI.

**Windows-specific browser bootstrap:**
- Files: `scripts/browser_daemon.py:43`, `scripts/launch_desktop_edge.py:60-63`
- Why fragile: hardcoded `C:\Program Files (x86)\...\msedge.exe` and
  `C:\Users\Sachin\.tweetytweets\edge-profile`; ignores `CHROME_PATH`/`BROWSER_PROFILE`, so Linux
  (Docker/VPS) and other Windows users take untested paths.
- Safe modification: route all executable/profile resolution through `settings.find_chrome()` and
  `settings.profile_dir()`; delete the tracked launcher or make it a generated template.
- Test coverage: `tests/test_browser_daemon.py` cannot validate real paths.

**`post.py` composer flow:**
- Files: `scripts/post.py:314-339`, `:434-560`
- Why fragile: double activation, manual `page.__aexit__`, unguarded `json.loads`, and verification
  that depends on timeline readback timing. A single failure leaves the composer open and the ledger
  inconsistent.
- Safe modification: one click path, explicit close in `finally`, and a single atomic ledger write
  after verification.
- Test coverage: no test drives a real composer; timeout/duplicate branches are untested.

**Guardrail enforcement is opt-in by call site:**
- Files: `scripts/validator.py`, `scripts/due.py`, `scripts/post.py`, `scripts/publish_now.py`,
  `scripts/autoposter.py`
- Why fragile: `publish_now.py` contains zero references to `validator`, and `due.py` validates only
  the root text, not per-platform drafts. New entry points can bypass all checks by calling adapters
  directly.
- Safe modification: enforce validation inside `PlatformAdapter.publish` (or a shared dispatcher),
  with an explicit `--skip-guardrails` override that is logged.
- Test coverage: `tests/test_guardrails.py` covers validator units, not bypass paths.

**Config is both data and executable policy:**
- Files: `config.json`, `scripts/settings.py`, `scripts/wizard.py`
- Why fragile: host-specific absolute paths, inline secrets, and toggles that some modules ignore
  (`dry_run`, `notifications`, `premium`, `require_verified_source`). One hand edit can silently
  change publishing behavior.
- Safe modification: add a JSON schema with defaults and validation, fail fast on unknown keys, and
  migrate path values to relative/env-driven ones.
- Test coverage: wizard tests use fixtures, not the real config shape.

**Docker entrypoint assumptions:**
- Files: `scripts/docker-entrypoint.sh`, `docker-compose.yml`
- Why fragile: it checks for `/app/.env` and `/app/state.json` while compose bind-mounts
  `state.json` and supplies `.env` via `env_file` (which does not create `/app/.env`), and it points
  at a missing `.env.example`. Behavior differs between compose and `docker run`.
- Safe modification: make the entrypoint validate env vars, not files; provide `.env.example` and a
  compose profile for local secrets.
- Test coverage: `tests/test_docker_config.py` asserts strings in YAML/Dockerfile, never runs the
  image.

## Scaling Limits

**Single browser port/profile:**
- Current capacity: one CDP endpoint (default 9444) and one profile directory.
- Limit: concurrent publishes or two daemons collide on the same tabs and cookies; tab leaks from
  failed runs accumulate.
- Scaling path: one browser context per platform, configurable ports, and a supervisor that
  recycles contexts.

**Flat-file state and plans:**
- Current capacity: 25 posts, a few dozen plan files.
- Limit: full-file rewrite per status update; `due()` scans every plan each tick; no retention.
- Scaling path: SQLite (WAL) or per-date files with an index, plus archival.

**One process, five-minute cadence:**
- Current capacity: roughly 4 slots/day, 4 platforms.
- Limit: a pipeline run longer than 5 minutes delays the next autoposter tick; a hung subprocess
  stalls the daemon indefinitely (no timeout).
- Scaling path: separate scheduler and worker, job queue with visibility timeouts, and health
  checks on each stage.

**Account-level platform limits:**
- Current capacity: one account per platform, no quota tracking.
- Limit: X/LinkedIn rate limits or warmup caps cause silent guardrail stalls (see Known Bugs).
- Scaling path: persist quota/warmup counters in the ledger and expose them in `doctor.py`.

**No horizontal observability:**
- Current capacity: stdout prints only; logs are not rotated or shipped.
- Limit: failures across long-running daemons are undiagnosable after the fact.
- Scaling path: structured JSON logs with correlation IDs, plus a metrics endpoint or log shipper.

## Dependencies at Risk

**Unpinned Python dependencies:**
- Risk: `requirements.txt` uses `>=` for websockets, Pillow, PyYAML, requests, pytest, and
  pytest-asyncio; no lock file or hashes.
- Impact: a major Pillow/websockets release can break rendering or CDP silently between installs.
- Migration plan: add a constraints/lock file (`pip-compile` or `uv lock`) and Dependabot/Renovate.

**Debian Chromium in the image:**
- Risk: `chromium` comes from the floating `python:3.12-slim-bookworm` base and Debian repos; CDP
  behavior and default flags change with updates.
- Impact: selectors and headless behavior can regress on rebuild without any code change.
- Migration plan: pin the base digest and Chromium version; run a container smoke test in CI.

**Hardcoded Edge assumptions:**
- Risk: `browser_daemon.py` and `launch_desktop_edge.py` assume Edge on Windows at a fixed path.
- Impact: non-Windows hosts and Edge-less machines fail before any adapter runs.
- Migration plan: detect Chrome/Chromium/Edge through `settings.find_chrome()` only; remove the
  tracked launcher.

**Optional `requests` dependency:**
- Risk: declared but most HTTP uses `urllib`; divergence creates two timeout/retry behaviors.
- Impact: inconsistent error handling and untested paths.
- Migration plan: standardize on one client with explicit timeouts and retries.

**No dependency or secret scanning in CI:**
- Risk: `.github/workflows/ci.yml` runs tests only.
- Impact: vulnerable or leaked dependencies go unnoticed.
- Migration plan: add `pip-audit` and a secret scan (gitleaks) as required checks.

## Missing Critical Features

**Enforced safe mode:**
- Problem: `dry_run` exists in config but does not gate publishing; there is no global kill switch.
- Blocks: safe onboarding, demos, and recovery after a bad deploy.

**Reconciliation for ambiguous publishes:**
- Problem: timeouts/readback failures are recorded as failures without checking whether the post
  landed.
- Blocks: reliable retries; every ambiguous failure risks a duplicate.

**Idempotency and cross-process locking:**
- Problem: no lock or idempotency key around ledger, plan, and publish operations.
- Blocks: running cron + daemon, or two autoposters, without double-posting.

**Credential onboarding contract:**
- Problem: `.env.example` is missing; `SECURITY.md` and the entrypoint reference it.
- Blocks: reproducible setup and Docker first-run without reading source.

**Per-platform quota/warmup accounting:**
- Problem: warmup caps are checked but not persisted or surfaced; platform rate limits (LinkedIn)
  are not enforced.
- Blocks: predictable autonomous cadence.

**Failure alerting for blocked/idle states:**
- Problem: notifications fire on publish attempts, not on guardrail blocks, parse failures, or a
  daemon stuck IDLE for a day.
- Blocks: knowing that automation silently stopped.

**Structured observability:**
- Problem: prints only; no correlation IDs, metrics, or log rotation.
- Blocks: post-incident diagnosis and trend analysis.

## Test Coverage Gaps

**Manual publish path (`publish_now`):**
- What's not tested: timeout behavior, thread cancellation, partial platform success, reconciliation,
  guardrail bypass.
- Files: `scripts/publish_now.py`, `tests/` (no `test_publish_now.py`)
- Risk: the timeout bug and duplicate-publish behavior ship unnoticed.
- Priority: High

**Daemon scheduler:**
- What's not tested: pipeline trigger conditions, subprocess failures/hangs, `dry_run` propagation,
  restart behavior, `--once`.
- Files: `scripts/daemon.py` (no dedicated test)
- Risk: the production entrypoint is the least-exercised module.
- Priority: High

**Real swipe schema integration:**
- What's not tested: `research.collect()` output consumed by `generate.load_daily_swipe()` and
  `pipeline` slicing.
- Files: `tests/test_pipeline.py`, `tests/test_generate.py`, `scripts/research.py`
- Risk: the dict/list mismatch only appears with a populated `swipe/` directory.
- Priority: High

**Concurrency and crash safety:**
- What's not tested: simultaneous ledger writers, atomic replace under interruption, corrupt JSON
  recovery, plan writes during a tick.
- Files: `tests/test_ledger.py`, `scripts/ledger.py`, `scripts/due.py`
- Risk: data loss and duplicate posts under normal daemon overlap.
- Priority: High

**Secret handling and redaction:**
- What's not tested: `.env` precedence, token redaction in logs/notifications, image layer contents.
- Files: `tests/test_notify_webhook.py`, `tests/test_llm.py`, `Dockerfile`
- Risk: credential leakage in logs and images.
- Priority: High

**Docker runtime behavior:**
- What's not tested: browser profile persistence, `BROWSER_PROFILE`/`CHROME_PATH` honoring,
  non-root execution, entrypoint env validation, absence of secrets in the image.
- Files: `tests/test_docker_config.py`, `Dockerfile`, `docker-compose.yml`,
  `scripts/docker-entrypoint.sh`
- Risk: tests pass while the documented deployment is broken.
- Priority: High

**LinkedIn rate limiting:**
- What's not tested: Schema v2 timing enforcement; existing fixtures use legacy `outcomes`/`platform`
  records.
- Files: `tests/test_linkedin.py`, `adapters/linkedin.py:217-232`
- Risk: the four-hour guard never triggers in production.
- Priority: Medium

**X AI-update header and `kind` propagation:**
- What's not tested: `PublishPayload.extra_metadata["kind"]` reaching `post.do_post` through the
  adapter.
- Files: `tests/test_adapters.py`, `adapters/x.py`, `scripts/autoposter.py`
- Risk: the daily series loses its header/day counter when published autonomously.
- Priority: Medium

**Repurposer vs guardrail consistency:**
- What's not tested: every `repurpose_topic` output passes `validate_draft_guardrails` for its
  target platform (the Threads CTA contradiction).
- Files: `tests/test_repurposer.py`, `tests/test_guardrails.py`, `scripts/repurpose.py`
- Risk: pipeline-generated drafts are rejected at publish time.
- Priority: Medium

**Browser/selector drift:**
- What's not tested: live DOM smoke tests, selector fallbacks, screenshot/HTML artifact capture.
- Files: `tests/test_adapters.py`, `tests/test_threads.py`, `tests/test_linkedin.py`
- Risk: upstream UI changes break publishing with only mocked tests passing.
- Priority: Medium

---

*Concerns audit: 2026-10-20*
