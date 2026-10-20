# Coding Conventions

**Analysis Date:** 2026-10-20

## Naming Patterns

**Files:**
- Modules are `snake_case.py` and named after the domain concept they implement: `scripts/prereq_check.py`, `scripts/voice_profile.py`, `render/infocard.py`.
- Platform adapters use the exact lowercase platform identifier as the filename: `adapters/x.py`, `adapters/bluesky.py`, `adapters/linkedin.py`, `adapters/threads.py`.
- Tests mirror the module under test: `scripts/ledger.py` → `tests/test_ledger.py`; `render/carousel.py` → `tests/test_carousel.py`.
- Render templates are lowercase snake_case HTML: `render/card_template.html`, `render/template.html`.
- Runnable CLI modules carry a shebang `#!/usr/bin/env python` (e.g. `scripts/ledger.py`, `scripts/due.py`, `scripts/post.py`, `scripts/autoposter.py`).

**Functions:**
- Functions and methods are `snake_case` verb phrases: `load_state`, `save_state`, `make_plan`, `run_daily_pipeline`, `validate_draft_guardrails`.
- Private helpers use a single leading underscore: `_ensure_session` (`adapters/bluesky.py`), `_normalize_text_for_comparison` (`scripts/validator.py`), `_clean_text` (`render/cards.py`), `_open_stealth` (`adapters/linkedin.py`).
- Factories/builders use `build_*`, `create_*`, `generate_*`: `build_card_slides` (`render/cards.py`), `create_carousel_pdf` (`render/carousel.py`), `generate_standard_slides` (`render/carousel.py`), `generate_topic_from_items` (`scripts/generate.py`).
- Resolvers use `resolve_*`: `resolve_model`, `resolve_api_key`, `resolve_provider` (`scripts/llm.py`).
- Predicates/queries use `is_*`, `has_*`, `check_*`, `verify_*`: `is_platform_done`, `get_pending_platforms` (`scripts/ledger.py`), `check_duplicate_post`, `verify_source_trace` (`scripts/validator.py`).
- Every executable module exposes a `main()` entry point (`scripts/validator.py`, `scripts/due.py`, `scripts/post.py`, `render/carousel.py`).

**Variables:**
- Constants are `UPPER_SNAKE_CASE` declared after imports: `DEFAULT_TIMEOUT`, `USER_AGENT` (`scripts/validator.py`, `scripts/llm.py`, `scripts/notify_webhook.py`), `ASSUMED_LIMIT` (`scripts/settings.py`), `BSKY_PUBLIC_API`, `URL_REGEX`, `MENTION_REGEX` (`adapters/bluesky.py`).
- Path constants are uppercase: `ROOT`, `STATE_PATH`, `CONFIG_PATH`, `EXAMPLE_PATH`, `STATE`, `SHOTS`, `PLANS`, `TICK_FILE` (`scripts/settings.py`, `scripts/ledger.py`, `scripts/post.py`, `scripts/due.py`).
- Embedded JavaScript snippets are uppercase with a `_JS` suffix: `LOGIN_JS`, `FOCUS_JS`, `COMPOSE_STATE_JS`, `PROFILE_JS` (`scripts/post.py`); `CHECK_SESSION_JS`, `STEALTH_JS`, `SUBMIT_POST_JS` (`adapters/linkedin.py`).
- CSS/DOM selector constants are uppercase: `EDITOR`, `POST_BTN`, `FILE_INPUT` (`scripts/post.py`).
- Short local names are conventional and reused: `cfg` for merged config, `st` for state dict, `res`/`r` for results, `p` for a post/point/path, `idx` for loop index, `msg` for human-readable message, `exc`/`err` for caught exceptions.
- Collection locals are annotated when non-trivial: `facets: list[dict[str, Any]]`, `points: list[str]`, `seen: set[str]`.

**Types:**
- Cross-module contracts are frozen/defaulted dataclasses in `adapters/base.py`: `PlatformCapabilities`, `PublishPayload`, `PublishResult`.
- Domain errors are exception classes ending in `Error`, all inheriting a shared base: `GuardRailError` → `CharacterLimitNotMeasuredError`, `EngagementBaitError`, `FabricatedClaimError`, `DuplicatePostError`, `HandleMismatchError`, `AccountWarmupError` (`scripts/validator.py`).
- Modern union syntax is mandatory (Python 3.10+): `str | None`, `Path | None`, `dict[str, Any] | None`; no `Optional[...]`/`Union[...]`.
- Validation functions return `tuple[bool, str]` (status + actionable message); multi-error validation returns `tuple[bool, list[str]]` (`validate_draft_guardrails`).
- `from __future__ import annotations` is the norm at the top of modules (`scripts/llm.py`, `scripts/ledger.py`, `adapters/bluesky.py`, `render/carousel.py`). Keep it when adding new modules.

## Code Style

**Formatting:**
- No formatter is configured. There is no `pyproject.toml`, `.ruff.toml`, `.flake8`, `setup.cfg`, `.pre-commit-config.yaml`, `black`/`isort` config, or `mypy` config in the repository.
- PEP 8 is the stated standard in `CONTRIBUTING.md`: 4-space indentation, double-quoted strings, f-strings for interpolation, trailing commas in multi-line literals and calls.
- Line length is not enforced; typical lines run 88–120 characters. Long calls are split with parenthesized continuation (`adapters/bluesky.py`, `scripts/validator.py`) or backslash continuation for stacked decorators/context managers in tests (`tests/test_pipeline.py`).
- UTF-8 file I/O is always explicit: `read_text(encoding="utf-8")`, `write_text(..., encoding="utf-8")`.
- JSON persistence uses `json.dumps(data, indent=2, ensure_ascii=False)` (`scripts/ledger.py`, `scripts/settings.py`, `scripts/pipeline.py`).
- Windows console safety uses a guarded reconfigure: `if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")` (`scripts/due.py`, `scripts/post.py`).
- Import placement is module-top. Do not copy the mid-file `import base64` at `adapters/base.py:28`; it is an outlier.

**Linting:**
- No linter is configured or run in CI. `.github/workflows/ci.yml` runs tests only.
- The de facto lint rules are the `CONTRIBUTING.md` constraints: no hardcoded host paths, no third-party vendor SDKs, no secrets in the repo, type annotations on public functions.
- Unused-import suppression uses `# noqa: E402` when imports must follow `sys.path` manipulation (`scripts/ledger.py`, `scripts/doctor.py`).

## Import Organization

**Order:**
1. `from __future__ import annotations`
2. Standard library only, alphabetical: `argparse`, `asyncio`, `json`, `os`, `re`, `sys`, `urllib.error`, `urllib.request`, `datetime`, `pathlib`, `typing`.
3. Blank line, then local absolute imports: `from adapters.base import ...`, `from scripts import settings`, `from render import create_infocard`.
4. Path bootstrap before local imports in any module runnable as a script:
   ```python
   ROOT = Path(__file__).resolve().parent.parent
   if str(ROOT) not in sys.path:
       sys.path.insert(0, str(ROOT))
   ```
   Examples: `scripts/settings.py:18-20`, `scripts/ledger.py:20-25`, `scripts/pipeline.py:20-22`, `setup.py:12-16`.
5. Dual-mode import fallback so a module works both as `python scripts/x.py` and as `scripts.x`:
   ```python
   try:
       from scripts import settings
       from scripts import due
       from scripts import generate
   except ImportError:
       import settings
       import due
       import generate
   ```
   Examples: `scripts/pipeline.py:24-35`, `scripts/autoposter.py:28-37`, `scripts/post.py:36-56`.
6. Deferred imports inside functions when needed to avoid import cycles: `settings.get_active_adapters` imports each adapter lazily (`scripts/settings.py:289-320`); `scripts/validator.py:379-383` imports `settings` inside a check.

**Path Aliases:**
- None. All imports are absolute package paths (`adapters.*`, `scripts.*`, `render.*`).
- `scripts/` is an implicit namespace package (no `scripts/__init__.py`); import it as `from scripts import ledger`, never with a relative `from . import`.
- Package barrels exist only for `adapters` and `render`: `adapters/__init__.py`, `render/__init__.py`.

## Error Handling

**Patterns:**
- Adapter boundary never raises. `publish`, `check_session`, and `verify` catch `Exception` and return a structured result:
  ```python
  except Exception as exc:
      return PublishResult(platform="bluesky", success=False, error=str(exc))
  ```
  (`adapters/bluesky.py:313-318`; identical shape in `adapters/x.py:89-94`, `adapters/threads.py`, `adapters/linkedin.py`.)
- `check_session` returns a dict with a stable contract: `{"ok": bool, "platform": str, "handle": str | None, "error": str | None}` (`adapters/x.py:43-57`, `adapters/bluesky.py:201-215`).
- Validation APIs return `(False, "actionable message")` instead of raising, e.g. `validate_bluesky_credentials`, `validate_llm_key`, `validate_webhook` in `scripts/validator.py`.
- Policy enforcement raises typed exceptions, but only when `raise_on_error=True`; otherwise errors accumulate and return `(False, errors)` (`validate_draft_guardrails`, `scripts/validator.py:534-621`).
- Secrets are redacted in error strings before they can be printed: `.replace(val, "[REDACTED_TOKEN]")` (`scripts/validator.py:251-260`).
- Catch specific exceptions where behavior differs: `urllib.error.HTTPError` is parsed for a provider message, then `URLError`/`Exception` produces a connection message (`scripts/validator.py`, `adapters/bluesky.py:164-173`). Browser read-back catches `(CDPError, OSError, asyncio.TimeoutError)` (`scripts/post.py:510`, `scripts/post.py:542`).
- Best-effort side effects swallow deliberately, with a comment or narrow scope: artifact capture in `adapters/base.py:43-64`, `.env` parsing in `scripts/llm.py:51-67`.
- CLI/config failures exit explicitly: `raise SystemExit(2)` when `config.json` is required but missing (`scripts/settings.py:95-110`); `sys.exit(0 if ok else 1)` for validator commands (`scripts/validator.py:653-655`).
- Browser/websocket resources are released in `finally`:
  ```python
  finally:
      await page.__aexit__(None, None, None)
  ```
  (`adapters/linkedin.py:273-274`, `scripts/post.py:498-499`.)
- State writes must go through the atomic ledger: `scripts/ledger.py:113-121` writes a temp file then `tmp_path.replace(target)`. Do not add direct `state.json.write_text(...)` calls; `scripts/post.py:72-79` still has legacy local helpers and should not be used as the pattern for new code.
- Configuration read failures degrade gracefully: `settings.load()` merges user config over `DEFAULTS` with `_merged()` and falls back to defaults when the file is absent (`scripts/settings.py:85-110`).

## Logging

**Framework:** `print()` to stdout/stderr; no `logging` module and no logger objects anywhere in `scripts/`, `adapters/`, or `render/`.

**Patterns:**
- Machine-readable results go to stdout as JSON: `print(json.dumps(out, indent=2, ensure_ascii=False))` (`scripts/post.py:571-615`), `scripts/due.py` prints either `IDLE` or a JSON draft.
- Human progress lines use a bracketed subsystem tag: `[PIPELINE]`, `[PLAN]`, `[CARDS]`, `[CAROUSEL]`, `[NOTIFY]`, `[DAEMON]`, `[ERROR]` (`scripts/pipeline.py:70-103`, `render/cards.py:230`, `render/carousel.py:521`, `scripts/notify_webhook.py:157-211`, `scripts/browser_daemon.py:86-103`).
- Wizard UX uses three markers: `[+]` success, `[!]` warning/failure, `[*]` informational (`scripts/wizard.py:259-539`).
- Non-fatal warnings go to `stderr`, often prefixed with `  !` (`scripts/post.py:511`, `scripts/research.py:208-275`, `scripts/browser.py:264-271`) or `[WARN]` (`adapters/linkedin.py:534`).
- Long-running loops flush explicitly: `print(..., file=sys.stderr, flush=True)` (`scripts/publish_now.py:76`).
- Operator-facing alerting is separate from logging: `scripts/notify_webhook.py` sends Telegram/Discord events, and `scripts/notify.py` wraps it for publish/session events. Tests globally stub these (see `tests/conftest.py`).

## Comments

**When to Comment:**
- Every module, class, and public function has a docstring summarizing purpose; module docstrings often include a numbered flow (see `scripts/pipeline.py:1-10`, `scripts/ledger.py:1-10`, `scripts/due.py:1-20`).
- Orchestrators use numbered step comments mirroring the flow: `# 1. Health check browser daemon`, `# 2. Collect swipe intelligence`, `# 3. Ensure plan exists` (`scripts/pipeline.py:72-99`), and numbered checks in `scripts/validator.py:546-617`.
- Section banners separate unrelated concerns: `# ------------------------------------------------------------------ Guard Rails` (`scripts/validator.py:287`), `# ------------------------------------------------------------------ ledger` (`scripts/post.py:70`).
- Comments explain constraints and reasons, not restatements: UTF-8 byte-offset rationale in `adapters/bluesky.py:33-38`, security mitigation references such as `# Threat mitigation: Sanitize model_id ... (07-SECURITY.md)` (`scripts/validator.py:159`), and `GUARDRAIL:` labels for invariants (`scripts/llm.py:73`).
- Inline comments justify magic numbers and tolerances: card-count thresholds (`scripts/generate.py:56-70`), warm-up limits (`scripts/validator.py:481-531`).

**JSDoc/TSDoc:**
- Python docstrings are used, not a formal doc generator. Style is a one-line summary, optionally followed by `Args:`/`Returns:` in adapter contract methods (`adapters/base.py:82-114`).
- No Sphinx/Google/MkDocs directives and no type duplication in docstrings; types live in signatures.

## Function Design

**Size:** Small pure helpers dominate (`format_x`, `extract_key_takeaways`, `_normalize_text_for_comparison`). Orchestrators and browser state machines are allowed to be long when they mirror a single UI flow, but are decomposed into named steps: `scripts/post.py` splits `do_post` into `_open`, `_insert_text`, `_attach_image`, `_click_post`, `_read_profile`.

**Parameters:**
- Keyword arguments for optional behavior: `force=False` (`scripts/pipeline.py:38`), `generate_media=True` (`scripts/repurpose.py` call site in `scripts/pipeline.py:50-56`), `raise_on_error=True` (`scripts/validator.py:534`), `auto_save=True` (`scripts/ledger.py:161`), `dry_run` (`scripts/autoposter.py`).
- Dependency injection via optional args for paths/clients: `path: Path | None = None` (`scripts/ledger.py:86`), `cfg: dict | None = None` (`scripts/settings.py`), `port: int | None = None` (`adapters/x.py`).
- Timeouts are parameters with module constants as defaults: `timeout: float = DEFAULT_TIMEOUT` (`scripts/validator.py`, `scripts/llm.py`, `scripts/notify_webhook.py`).

**Return Values:**
- Adapter methods return dataclasses; never raw tuples.
- Parsing/synthesis functions return plain dicts with documented keys (`generate_topic_from_items`, `repurpose_topic`), and renderers return `Path` to the generated artifact (`create_infocard`, `create_carousel_pdf`).
- Validators return `(bool, message)`; query helpers return the object or `None` (`get_slot_entry`, `get_platform_status` in `scripts/ledger.py`).
- CLI functions return process-style ints where a runner consumes them (`main() -> int` in `scripts/autoposter.py`).

## Module Design

**Exports:**
- Public API is explicit in package barrels with `__all__`: `adapters/__init__.py:14-23`, `render/__init__.py:4`.
- Modules outside barrels are imported by full path; there is no catch-all `scripts/__init__.py`.
- Constants and helpers intended to be private are underscore-prefixed and not re-exported.
- Shared configuration is read only through `scripts.settings` (`load`, `limit`, `get_platforms`, `get_active_adapters`, `profile_dir`, `find_chrome`, `tzinfo`). New config keys belong in `DEFAULTS` in `scripts/settings.py:32-82` and in `config.example.json`; never read `config.json` directly from a new module.
- Persistent state is read/written only through `scripts.ledger` (`load_state`, `save_state`, `record_platform_status`, `get_pending_platforms`).

**Barrel Files:**
- `adapters/__init__.py` re-exports the four adapter classes plus the three base contracts.
- `render/__init__.py` re-exports `create_infocard`, `create_carousel_pdf`, `build_carousel_html`.
- No barrel file for `tests/` or `scripts/`; tests import concrete modules, and scripts import sibling modules directly.

---

*Convention analysis: 2026-10-20*
