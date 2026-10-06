# Task 3 Brief: Interactive CLI Onboarding Wizard + Non-Interactive CI Fallback

## Goal
Implement `setup.py`, `scripts/wizard.py`, and `tests/test_wizard.py`.
Provides an interactive 6-step CLI onboarding wizard that outputs `.env` and `config.json` while verifying live credentials via `scripts/validator.py`.
Fully supports `--non-interactive` and `--test-mode` flags for unattended CI and testing environments, and guarantees `state.json` and `.env` file existence via `scripts/prereq_check.py`.

## Files
- **Create:** `setup.py` (entrypoint invoking `scripts.wizard.main()`)
- **Create:** `scripts/wizard.py`
- **Create:** `tests/test_wizard.py`

## Interfaces & Contracts

```python
from pathlib import Path
from typing import Any

def run_wizard(
    non_interactive: bool = False,
    test_mode: bool = False,
    root: Path | None = None,
    inputs: list[str] | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Runs the 6-step configuration wizard.
    Returns (config_data, env_vars).
    Writes to config.json and .env in root.
    Calls prereq_check.guarantee_state_files(root).
    """

def detect_system_timezone() -> str:
    """Auto-detects host system timezone name with fallback to 'local'."""
```

## TDD Steps
1. Write `tests/test_wizard.py` covering:
   - `test_wizard_non_interactive_creates_files()`: verifies running with `--non-interactive` creates `config.json` and `.env` and calls `guarantee_state_files()`.
   - `test_wizard_interactive_simulation()`: mocks `input` responses across all 6 steps and verifies resulting config & env contents.
   - `test_wizard_timezone_detection()`: verifies detected timezone.
   - `test_wizard_dry_run_flag()`: verifies dry_run mode in config.
2. Run test to verify it fails:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_wizard.py`
3. Implement `scripts/wizard.py` and `setup.py`.
4. Run test to verify it passes:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_wizard.py`
5. Commit:
   `git add setup.py scripts/wizard.py tests/test_wizard.py`
   `git commit -m "feat(wizard): implement interactive onboarding wizard with non-interactive CI fallback"`
6. Write report to `.superpowers/sdd/onboarding-deployment-execution-plan/task-3-report.md`.
