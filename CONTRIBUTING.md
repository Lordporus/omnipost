# Contributing to OmniPost

Thank you for your interest in contributing to **OmniPost V2.0**! OmniPost is an autonomous, sovereign, zero-cost cross-platform publishing syndicate built for technical operators and AI agents.

We welcome bug reports, adapter improvements, documentation enhancements, and pull requests that respect our core architectural principles.

---

## Core Architectural Guarantees

Before proposing changes, please note our foundational design constraints:

1. **Zero API Cost Core:** Upstream browser automation (X, LinkedIn, Threads) and Bluesky (ATProto XRPC) must remain 100% free of SaaS fees and commercial API subscriptions.
2. **Zero Bloat / Standard Library First:** The LLM client (`scripts/llm.py`) and network integrations must use Python's standard library (`urllib.request`) rather than adding heavy third-party vendor SDKs (`google-generativeai`, `openai`, `anthropic`).
3. **Hermetic & Isolated Testing:** Unit tests must never initiate real network requests, never read live API keys from disk, and never modify persistent state files. All external protocols and subprocesses must be mocked.
4. **Cross-Platform Portability:** Code must run consistently across Windows, macOS, and Linux. Never hardcode OS-specific paths (e.g. `C:\Users\...`); always use dynamic path resolution via `Path.home()` or the repository `ROOT`.
5. **Atomic State Operations:** All mutations to `state.json` must be atomic (writing to a temporary file in the same directory and replacing atomically) to prevent state file corruption during abrupt shutdowns.

---

## Prerequisites & Development Setup

### System Requirements
- **Python:** 3.10, 3.11, or 3.12 (sys.version >= 3.10 required for union types and `zoneinfo`)
- **Browser:** Microsoft Edge, Google Chrome, or Chromium (with remote debugging port support)
- **Git:** Git 2.30+

### Clone & Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Lordporus/omnipost.git
   cd omnipost
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # On macOS/Linux:
   python3 -m venv .venv
   source .venv/bin/activate

   # On Windows (PowerShell):
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify your local environment:**
   ```bash
   python scripts/prereq_check.py
   python scripts/doctor.py
   ```

---

## Running the Test Suite

OmniPost uses `pytest` with hermetic root path resolution configured in `pytest.ini`.

```bash
# Run the entire test suite
pytest -v

# Run a specific test module
pytest tests/test_llm.py -v
pytest tests/test_browser_daemon.py -v
pytest tests/test_wizard.py -v

# Run with test coverage
pytest --cov=. tests/
```

All 214+ tests should pass cleanly without any live network credentials or active browser instances.

---

## Coding Guidelines

- **Type Annotations:** Use Python 3.10+ typing syntax (`X | Y`, `from __future__ import annotations`).
- **Code Style:** Follow PEP 8 standards with 4-space indentation and clean docstrings.
- **Error Handling:** When interfacing with external web UIs or network endpoints, handle specific exceptions (`urllib.error.URLError`, `urllib.error.HTTPError`, `json.JSONDecodeError`, `TimeoutError`), provide actionable diagnostics, and implement graceful heuristic fallbacks.
- **DOM Selector Maintenance:** If platforms update their UI classes or attributes, update the corresponding adapter in `adapters/` and include clear fallback selectors with descriptive failure reasons.
- **No Secrets:** Never commit `.env`, `config.json` containing live tokens, or private session files. Keep `config.example.json` updated with placeholder values for any new configuration keys.

---

## Pull Request Checklist

Before submitting a pull request, please verify:

- [ ] All tests pass locally via `pytest -v`.
- [ ] System diagnostics succeed via `python scripts/prereq_check.py` and `python scripts/doctor.py`.
- [ ] No hardcoded host paths (e.g., `C:\Users\...` or `/home/username/...`) are introduced.
- [ ] Unit tests are added or updated to cover your changes with hermetic mocking.
- [ ] Commits follow Conventional Commits (e.g., `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`).
- [ ] Documentation (`README.md`, docstrings) has been updated if configuration keys or CLI arguments changed.
