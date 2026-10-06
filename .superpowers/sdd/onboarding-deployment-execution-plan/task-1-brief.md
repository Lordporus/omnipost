# Task 1 Brief: Prerequisite & Diagnostic Checker + State File Guard

## Goal
Implement `scripts/prereq_check.py`, update `scripts/doctor.py` to add `--healthcheck`, update `scripts/browser_daemon.py` to append container & Linux sandbox flags (`--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`), and write unit tests in `tests/test_prereq_check.py` and `tests/test_browser_daemon.py`.

## Files
- **Create:** `scripts/prereq_check.py`
- **Modify:** `scripts/doctor.py`
- **Modify:** `scripts/browser_daemon.py`
- **Create:** `tests/test_prereq_check.py`
- **Modify:** `tests/test_browser_daemon.py`

## Interfaces & Contracts

### 1. `scripts/prereq_check.py`
```python
from pathlib import Path
from typing import Any

def check_prerequisites(root: Path | None = None) -> dict[str, Any]:
    """Runs system diagnostics:
    - python: sys.version_info >= (3, 10)
    - git: shutil.which('git') is not None
    - browser: checks ['msedge', 'google-chrome', 'chromium-browser', 'chromium'] or settings.find_chrome()
    - docker: checks shutil.which('docker') and shutil.which('docker-compose') or 'docker compose'
    - port_9444: socket bind test on 127.0.0.1:9444
    - ledger_writable: atomic write & delete of .write_test.tmp
    - state_files_guaranteed: calls guarantee_state_files()
    """

def guarantee_state_files(root: Path | None = None) -> None:
    """Ensures state.json and .env exist as regular files.
    - If state.json or .env is a directory, raises ValueError.
    - If state.json missing, writes '{}'.
    - If .env missing, writes empty file.
    - Ensures drafts/, swipe/, scratch/ directories exist.
    """
```

### 2. `scripts/doctor.py`
- Add `--healthcheck` flag:
  If any check returns `BAD`, exit code 1. Otherwise exit code 0.

### 3. `scripts/browser_daemon.py`
- Detect Linux, Docker (`IS_DOCKER=1`), or headless environment (`headless=True` or `HEADLESS=1`).
- When true, append `--no-sandbox`, `--disable-dev-shm-usage`, and `--disable-gpu` to browser launch arguments.

## TDD Steps
1. Write `tests/test_prereq_check.py`.
2. Run test to verify it fails:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_prereq_check.py`
3. Implement `scripts/prereq_check.py`, update `scripts/doctor.py`, update `scripts/browser_daemon.py`.
4. Update `tests/test_browser_daemon.py` with `test_ensure_browser_running_linux_flags`.
5. Run tests to verify all pass:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_prereq_check.py tests/test_browser_daemon.py`
6. Run full pytest suite across repo to guarantee no regressions.
7. Atomic commit:
   `git add scripts/prereq_check.py scripts/doctor.py scripts/browser_daemon.py tests/test_prereq_check.py tests/test_browser_daemon.py`
   `git commit -m "feat(prereq): implement prerequisite checker, state file guards, and container browser flags"`
8. Write report to `.superpowers/sdd/onboarding-deployment-execution-plan/task-1-report.md`.
