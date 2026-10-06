# Task 2 Brief: Live Credential & Multi-LLM Ping Engine

## Goal
Implement `scripts/validator.py` and `tests/test_validator.py`.
Provides zero-dependency validation functions for social platform credentials and AI providers with immediate live checks before saving keys.

## Files
- **Create:** `scripts/validator.py`
- **Create:** `tests/test_validator.py`

## Interfaces & Contracts

```python
from typing import Any

def validate_bluesky_credentials(identifier: str, app_password: str, timeout: float = 8.0) -> tuple[bool, str]:
    """Validates Bluesky handle and app password via ATProto server session endpoint."""

def validate_llm_key(provider: str, api_key: str, timeout: float = 8.0) -> tuple[bool, str]:
    """Validates Gemini, OpenAI, Claude, OpenRouter, or Local mode via 1-token / models endpoint."""

def validate_webhook(service: str, url_or_token: str, chat_id: str | None = None, timeout: float = 8.0) -> tuple[bool, str]:
    """Sends a minimal non-intrusive test message to Telegram or Discord."""
```

## TDD Steps
1. Write `tests/test_validator.py` with mock tests for all providers and error branches.
2. Run test to verify it fails:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_validator.py`
3. Implement `scripts/validator.py`.
4. Run test to verify it passes:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_validator.py`
5. Commit:
   `git add scripts/validator.py tests/test_validator.py`
   `git commit -m "feat(validator): add live credential, multi-LLM ping, and webhook validation engine"`
6. Write report to `.superpowers/sdd/onboarding-deployment-execution-plan/task-2-report.md`.
