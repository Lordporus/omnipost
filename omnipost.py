#!/usr/bin/env python
"""OmniPost - Root CLI Entrypoint.

Allows running OmniPost directly without package installation:
  python omnipost.py post
  python omnipost.py doctor
  python omnipost.py setup
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from omnipost.cli import main

if __name__ == "__main__":
    sys.exit(main())
