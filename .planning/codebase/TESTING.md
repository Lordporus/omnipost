# Testing Patterns

**Analysis Date:** 2026-10-20

## Test Framework

**Runner:**
- pytest >= 8.0.0 (`requirements.txt:14`), also compatible with stdlib `unittest.TestCase` suites.
- Config: `pytest.ini` — `pythonpath = .`, `testpaths = tests`. This makes repository-root imports (`from scripts import ledger`, `from adapters.base import ...`) work without per-file path setup.
- `pytest-asyncio >= 0.23.0` is installed (`requirements.txt:15`) but **not configured**: there is no `asyncio_mode` setting in `pytest.ini` and no `async def test_...` in `tests/`. Do not add async tests without first adding `asyncio_mode`/markers.
- CI: `.github/workflows/ci.yml` runs `pytest -v` on `ubuntu-latest` and `windows-latest` for Python 3.10, 3.11, 3.12, with `CI=true`, `HEADLESS=1`, and blank Telegram/Discord credentials.

**Assertion Library:**
- Stdlib `unittest` assertions (`self.assertEqual`, `self.assertTrue`, `self.assertRaises`, `self.assertIn`) in class-based suites.
- Plain `assert` statements in pytest-style modules (`tests/test_pipeline.py`, `tests/test_llm.py`, `tests/test_integration_e2e.py`).

**Run Commands:**
```bash
pytest -v                     # Run all tests (documented in CONTRIBUTING.md)
python -m pytest -v           # Equivalent, used in README.md
pytest tests/test_llm.py -v   # Run a single module
pytest --cov=. tests/         # Coverage (requires pytest-cov; not in requirements.txt)
```
- Baseline from `README.md`: 230 collected tests, all passing (`tests/` contains 31 test modules; `rg -c "def test_"` totals 230).

## Test File Organization

**Location:**
- Separate top-level `tests/` directory; no co-located tests in `scripts/`, `adapters/`, or `render/`.
- Flat layout: one module per production module, e.g. `scripts/validator.py` → `tests/test_validator.py`, `render/carousel.py` → `tests/test_carousel.py`, `adapters/threads.py` → `tests/test_threads.py`.
- Cross-cutting suites have descriptive names: `tests/test_integration_e2e.py`, `tests/test_multiplatform_adaptation.py`, `tests/test_retry_isolation.py`, `tests/test_guardrails.py`, `tests/test_docker_config.py`, `tests/test_vps_deployment.py`.

**Naming:**
- Files: `test_<module_or_feature>.py`.
- Classes: `Test<Feature>` (e.g. `TestStateLedger` in `tests/test_ledger.py`, `TestGuardRails` in `tests/test_guardrails.py`, `TestLinkedInCarouselAndVerification` in `tests/test_linkedin_carousel.py`).
- Methods/functions: `test_<behavior>_<condition>` with long descriptive names, e.g. `test_populate_daily_plan_skips_already_populated_slots` (`tests/test_pipeline.py`), `test_unicode_and_emojis_byte_slices` (`tests/test_bluesky.py`), `test_partial_failure_isolation_and_safe_retry` (`tests/test_integration_e2e.py`).
- Test doubles: `Mock<Thing>` classes (`MockPlatformAdapter` in `tests/test_integration_e2e.py`, `MockCompleteAdapter`/`MockIncompleteAdapter` in `tests/test_adapters.py`).

**Structure:**
```text
tests/
├── conftest.py                          # global autouse webhook isolation
├── test_adapters.py                     # adapter ABC + XAdapter
├── test_validator.py                    # credential/webhook/guardrail validation
├── test_ledger.py                       # state schema migration + atomic writes
├── test_llm.py                          # multi-provider synthesis (pytest style)
├── test_integration_e2e.py              # multi-platform lifecycle (pytest style)
├── test_retry_isolation.py              # partial-failure retry semantics
├── test_multiplatform_adaptation.py     # per-platform formatting invariants
├── test_carousel.py / test_carousel_rendering.py / test_infocard.py
├── test_docker_config.py / test_vps_deployment.py   # deployment file assertions
└── test_<module>.py                     # all remaining modules
```

## Test Structure

**Suite Organization:**
- Two coexisting styles. Roughly two-thirds of modules use `unittest.TestCase` classes with `setUp`/`tearDown`; 11 modules use module-level pytest functions with fixtures.
- Class style with temporary state:
  ```python
  class TestStateLedger(unittest.TestCase):
      """Test suite for state ledger migration, atomic writes, and per-platform status."""

      def setUp(self):
          self.temp_dir = TemporaryDirectory()
          self.test_state_file = Path(self.temp_dir.name) / "state.json"

      def tearDown(self):
          self.temp_dir.cleanup()
  ```
  (`tests/test_ledger.py:11-19`; same pattern in `tests/test_analytics.py`, `tests/test_feedback.py`, `tests/test_retry_isolation.py`.)
- Function style with pytest fixtures:
  ```python
  def test_full_e2e_pipeline_simulation(tmp_path):
      state_file = tmp_path / "state.json"
      state = ledger.load_state(state_file)
  ```
  (`tests/test_integration_e2e.py:73-76`; `tmp_path` also used in `tests/test_pipeline.py`, `tests/test_carousel_rendering.py`, `tests/test_generate.py`.)
- Test doubles that implement the real contract:
  ```python
  class MockPlatformAdapter(PlatformAdapter):
      """Configurable mock adapter for testing multi-platform orchestration."""

      def __init__(self, name: str, should_succeed: bool = True, max_chars: int = 500):
          self._name = name
          self.published_calls: list[PublishPayload] = []

      def publish(self, payload: PublishPayload) -> PublishResult:
          self.published_calls.append(payload)
          ...
  ```
  (`tests/test_integration_e2e.py:33-70`; a lighter, non-subclassing double is in `tests/test_retry_isolation.py:13-30`.)

**Patterns:**
- Setup: `setUp` with `TemporaryDirectory`, or `tmp_path` fixture for filesystem isolation.
- Teardown: `tearDown` calls `self.temp_dir.cleanup()`; temporary directories prevent touching the repo `state.json`.
- Assertions: exact-value assertions on structured dicts, plus invariants on generated content (length ceilings, required phrases) in `tests/test_multiplatform_adaptation.py`.
- Environment isolation is explicit: `patch.dict(os.environ, env, clear=True)` (`tests/test_notify_webhook.py:31`), `monkeypatch.setenv/delenv` (`tests/test_llm.py:40-80`), and manual removal of provider keys in `tests/test_wizard.py:27-41`.
- Each unittest module ends with:
  ```python
  if __name__ == "__main__":
      unittest.main()
  ```
- `tests/test_omnipost.py:20-28` is the only module that manually inserts `scripts/` into `sys.path`; prefer the `pytest.ini` `pythonpath` and absolute `scripts.*` imports for new tests.

## Mocking

**Framework:** stdlib `unittest.mock` only — `patch`, `MagicMock`, `AsyncMock`, `patch.object`. No `pytest-mock`, `responses`, `vcrpy`, `requests-mock`, or fixture-based HTTP recorders. No test hits the live network, a real browser, or a real credential.

**Patterns:**
- Patch at the point of use, using the full module path:
  ```python
  @patch("scripts.validator.urllib.request.urlopen")
  def test_success_200(self, mock_urlopen):
      mock_resp = MagicMock()
      mock_resp.read.return_value = json.dumps({
          "handle": "alice.bsky.social",
          "accessJwt": "jwt.sample",
      }).encode("utf-8")
      mock_resp.__enter__.return_value = mock_resp
      mock_urlopen.return_value = mock_resp
  ```
  (`tests/test_validator.py:26-40`; adapter equivalent in `tests/test_bluesky.py:69-83`.)
- Simulate HTTP failures with `side_effect` and a real `HTTPError` whose `fp` reads a JSON body:
  ```python
  mock_urlopen.side_effect = urllib.error.HTTPError(
      url="https://bsky.social/xrpc/com.atproto.server.createSession",
      code=401,
      msg="Unauthorized",
      hdrs={},
      fp=MagicMock(read=lambda: b'{"message": "Invalid identifier or password"}'),
  )
  ```
  (`tests/test_validator.py:44-50`, `tests/test_bluesky.py:87-93`.)
- Patch adapter internals to isolate orchestration from CDP:
  ```python
  @patch.object(BlueskyAdapter, "_ensure_session")
  @patch.object(BlueskyAdapter, "_request")
  @patch.object(BlueskyAdapter, "verify")
  def test_publish_text_success(self, mock_verify, mock_request, mock_session):
      ...
  ```
  (`tests/test_bluesky.py:98-120`; `@patch.object(ThreadsAdapter, "_async_verify", return_value=True)` in `tests/test_threads.py:54`.)
- Patch `asyncio.run` at the production module to keep tests synchronous:
  ```python
  with patch("render.carousel.asyncio.run") as mock_asyncio_run, patch("render.carousel._render_pdf_cdp"):
      mock_asyncio_run.return_value = output_pdf
  ```
  (`tests/test_carousel_rendering.py:116-119`; also `tests/test_carousel.py:55-61`, `tests/test_guardrails.py:200`.)
- Use `AsyncMock` for awaited browser/page dependencies:
  ```python
  mock_page = AsyncMock()
  mock_page.eval.return_value = json.dumps({"logged_in": True, "handle": "lordporus_ai"})
  ```
  (`tests/test_threads.py:28-33`; `@patch("scripts.browser.settle_page", new_callable=AsyncMock)` in `tests/test_linkedin.py:93`.)
- Patch module-level constants to redirect persistence:
  ```python
  with patch.object(ledger, "STATE_PATH", self.state_file), \
       patch("scripts.autoposter.ledger.STATE_PATH", self.state_file):
  ```
  (`tests/test_retry_isolation.py:77-78`; `patch("scripts.pipeline.ROOT", tmp_path)` in `tests/test_pipeline.py:64`.)
- Patch subprocess/OS boundaries instead of executing them: `patch("subprocess.Popen")` (`tests/test_browser_daemon.py`), `patch("subprocess.run")` (`tests/test_prereq_check.py`), `patch("sys.platform", "win32")` (`tests/test_browser_daemon.py:44`).

**What to Mock:**
- `urllib.request.urlopen` and network layer for every HTTP integration.
- CDP/browser entry points (`_open_stealth`, `ensure_chrome`, `settle_page`, `asyncio.run`).
- `subprocess.Popen`/`subprocess.run` and `sys.platform` for cross-platform launch logic.
- Filesystem roots and state paths whenever the code would write inside the repository.
- Webhook dispatch (globally, see `tests/conftest.py`).

**What NOT to Mock:**
- The unit under test — call the real pure function (`validate_draft_guardrails`, `extract_facets`, `parse_linkedin_payload`, `generate_standard_slides`).
- Adapter contract behavior when testing orchestration — implement a fake `PlatformAdapter` subclass (`MockPlatformAdapter`) instead of mocking each method.
- JSON serialization or `Path` operations; use real temp paths so atomic replace semantics are exercised (`tests/test_ledger.py:63-75`).
- Real `state.json`, real credentials, real browser sessions, and live APIs — never.

## Fixtures and Factories

**Test Data:**
- Inline literals are the default; no shared factory library or fixture directory.
- Reusable topic fixture:
  ```python
  @pytest.fixture
  def core_insight():
      return {
          "headline": "Browser Automation Over DevTools Protocol Eliminates $200/mo API Bills",
          "body": "Modern platforms like X and LinkedIn charge enterprise rates ...",
          "points": ["Direct WebSocket transport bypasses Selenium ...", ...],
          "takeaway": "Build sovereign developer tools before subscribing to cloud middleware.",
          "category": "DISTRIBUTED SYSTEMS",
      }
  ```
  (`tests/test_multiplatform_adaptation.py:24-36`.)
- Plans and legacy state are built inline per test, e.g. `legacy_data` in `tests/test_ledger.py:23-44` and `self.plan_data` in `tests/test_retry_isolation.py:47-65`.
- Temporary paths: `tmp_path` (pytest) or `TemporaryDirectory()` (unittest), always cleaned up.

**Location:**
- Global fixtures live only in `tests/conftest.py`.
- Module-scoped `autouse` fixtures isolate environment/network in `tests/test_llm.py:33-37`, `tests/test_notify_webhook.py:19-22`, and `tests/conftest.py:8-25`.
- There is no `tests/fixtures/` or `tests/data/` directory.

## Coverage

**Requirements:** None enforced. No coverage threshold, `.coveragerc`, or `--cov-fail-under` exists, and CI does not run coverage.

**View Coverage:**
```bash
pip install pytest-cov
pytest --cov=. tests/
```
`pytest-cov` is documented in `CONTRIBUTING.md:74-76` but is not listed in `requirements.txt`, so install it explicitly before use.

## Test Types

**Unit Tests:**
- Pure logic and module contracts: `tests/test_validator.py` (credential validation, guardrails), `tests/test_ledger.py` (migration, atomic save, per-platform status), `tests/test_llm.py` (provider/model resolution, JSON fence stripping), `tests/test_bluesky.py` (facet byte offsets), `tests/test_carousel.py`/`tests/test_infocard.py` (renderer helpers).
- Adapter capability/contract tests: `tests/test_adapters.py`, `tests/test_threads.py`, `tests/test_linkedin.py`.

**Integration Tests:**
- In-process, dependency-mocked flows: `tests/test_integration_e2e.py` (repurpose → mock adapters → ledger → verify, plus partial-failure retry), `tests/test_retry_isolation.py` (autoposter retries only failed platforms), `tests/test_multiplatform_adaptation.py` (four platform formats from one topic), `tests/test_carousel_rendering.py` (HTML → PDF binary signature → LinkedIn payload).
- Deployment/config integration is validated by reading and asserting on repository files: `tests/test_docker_config.py` (Dockerfile, `docker-compose.yml`, `scripts/docker-entrypoint.sh`), `tests/test_vps_deployment.py` (`scripts/run_vps.sh`, `systemd/omnipost.service`). These use `yaml.safe_load` and regex assertions rather than executing containers.

**E2E Tests:**
- No automated real-browser E2E. Browser flows are exercised manually through `scripts/test_adapter.py` and `scripts/wizard.py`; CI sets `HEADLESS=1` and blanks credentials.
- True network publishing is out of scope for `tests/`; never add a test that logs into X/LinkedIn/Threads/Bluesky.

## Common Patterns

**Async Testing:**
- No `async def test_...`; production wrappers expose sync APIs over `asyncio.run` (`adapters/x.py`, `adapters/linkedin.py`, `scripts/post.py`), and tests stay synchronous.
- Two accepted approaches:
  ```python
  # 1. Patch the production asyncio.run boundary
  with patch("render.carousel.asyncio.run") as mock_asyncio_run:
      mock_asyncio_run.return_value = output_pdf
      create_carousel_pdf(slides, output_path=output_pdf)
  ```
  ```python
  # 2. Patch the async dependency with an async function / AsyncMock
  @patch("scripts.post.session_info")
  def test_x_adapter_check_session_success(self, mock_session):
      async def fake_session():
          return {"handle": "OmniPostHQ", "tier": "free"}
      mock_session.side_effect = fake_session
  ```
  (`tests/test_carousel_rendering.py:116-119`, `tests/test_adapters.py:100-108`.)

**Error Testing:**
- `unittest` style: `with self.assertRaises(CharacterLimitNotMeasuredError):` (`tests/test_guardrails.py:62`), `with self.assertRaises(ValueError):` (`tests/test_carousel.py:52`).
- pytest style with message matching: `with pytest.raises(ValueError, match="state.json is a directory"):` (`tests/test_prereq_check.py:125`), `with pytest.raises(EngagementBaitError):` (`tests/test_integration_e2e.py:222`).
- Error paths assert the actionable message, not just the exception type: `self.assertIn("Invalid identifier or password", msg)` (`tests/test_validator.py:54`).
- Bulk-case validation uses loops inside one test rather than parametrization:
  ```python
  for sample in bait_samples:
      detected, msg = engagement_bait_pattern_detected(sample)
      self.assertTrue(detected, f"Failed to detect bait in: {sample}")
  ```
  (`tests/test_guardrails.py:28-41`.)

**Global Isolation Guardrail:**
- `tests/conftest.py:8-25` installs an autouse fixture that stubs `scripts.notify_webhook.dispatch_webhook`, `scripts.notify.dispatch_webhook`, and both `send_session_expired_alert` functions. `tests/test_notify_webhook.py` is explicitly exempt so it can test payload formatting against a mocked `urlopen`.
- New tests that trigger publish/session flows inherit this protection automatically; do not remove or weaken it.

**Time-Sensitive Tests:**
- Patch the module's `datetime` symbol instead of sleeping: `with patch("scripts.validator.datetime") as mock_dt:` (`tests/test_guardrails.py:162`).
- Avoid real `asyncio.sleep` in tests; patch the async boundary or the function that polls. No test intentionally waits on wall-clock time.

**Repository Hygiene:**
- `tests/test_wizard.py:20-48` uses `scratch/test_wizard_tmp` rather than `tmp_path` and removes it in `tearDown`; prefer `tmp_path` for new tests so failed runs cannot leave artifacts.
- Generated output directories (`drafts/`, `swipe/`, `shots/`, `scratch/`) are git-ignored, but tests must still avoid writing into them unless they clean up.

---

*Testing analysis: 2026-10-20*
