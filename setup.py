#!/usr/bin/env python
"""OmniPost V2.0 Setup & Onboarding CLI Entrypoint.

Dispatches to scripts.wizard.main() to run the interactive 6-step onboarding
wizard or headless non-interactive CI setup.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.wizard import main

if __name__ == "__main__":
    main()
