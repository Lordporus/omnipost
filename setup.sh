#!/usr/bin/env bash
set -e

echo "==================================================="
echo "OmniPost v2.5 - Local Setup & Onboarding Installer"
echo "==================================================="

# 1. Check for python3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

PY_VER=$(python3 --version)
echo "[*] Detected ${PY_VER}"

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# 3. Activate Virtual Environment
source .venv/bin/activate

# 4. Install Dependencies
echo "[*] Installing / updating dependencies from requirements.txt..."
python3 -m pip install --upgrade pip > /dev/null 2>&1 || true
pip install -r requirements.txt

# 5. Launch Wizard
echo ""
echo "==================================================="
echo "Launching Onboarding Wizard..."
echo "==================================================="
echo ""
python3 scripts/wizard.py
