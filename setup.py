#!/usr/bin/env python
"""OmniPost dual-purpose setup entrypoint.

Acts as standard setuptools packaging script when called by pip/build tools,
and dispatches to the onboarding wizard when run directly with wizard args.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

WIZARD_FLAGS = {"--non-interactive", "--test-mode", "--defaults", "--root"}


def is_wizard_call() -> bool:
    """Return True only if human user runs setup.py directly or test passes wizard flags."""
    if any(arg in WIZARD_FLAGS for arg in sys.argv[1:]):
        return True
    if len(sys.argv) == 1:
        return True
    return False


if __name__ == "__main__":
    if is_wizard_call():
        from scripts.wizard import main
        main()
    else:
        from setuptools import setup
        setup()
