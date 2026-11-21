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

SETUPTOOLS_COMMANDS = {
    "develop", "install", "bdist_wheel", "egg_info", "dist_info",
    "build", "sdist", "bdist", "check", "clean", "--help", "-h",
    "--help-commands", "--version",
}


def is_setuptools_call() -> bool:
    """Return True if sys.argv represents a setuptools/pip build invocation."""
    if len(sys.argv) > 1:
        first_arg = sys.argv[1].lower()
        if first_arg in SETUPTOOLS_COMMANDS:
            return True
        if any(cmd in sys.argv for cmd in ("dist_info", "egg_info", "bdist_wheel")):
            return True
    return False


if __name__ == "__main__":
    if is_setuptools_call():
        from setuptools import setup
        setup()
    else:
        from scripts.wizard import main
        main()
