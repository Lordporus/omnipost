#!/bin/bash
set -e

# OmniPost Automated 1-Click VPS Deployment & Provisioning Script
# Target OS: Debian / Ubuntu

echo "========================================="
echo " Starting OmniPost VPS Provisioning"
echo "========================================="

# Ensure script is run with superuser privileges
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run this script as root (e.g. sudo bash scripts/deploy_vps.sh)." >&2
    exit 1
fi

# 1. Update system repositories and install system packages
echo "Updating apt package list..."
apt-get update -y

echo "Installing required system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    chromium \
    xvfb \
    fonts-liberation \
    fonts-noto-color-emoji \
    curl \
    git

# 2. Setup application target directory (/opt/omnipost)
INSTALL_DIR="/opt/omnipost"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "${SCRIPT_DIR}" != "${INSTALL_DIR}" ]; then
    echo "Syncing OmniPost codebase to ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}"
    cp -r "${SCRIPT_DIR}/." "${INSTALL_DIR}/"
fi

cd "${INSTALL_DIR}"

# Ensure scripts are executable
chmod +x scripts/run_vps.sh scripts/deploy_vps.sh

# 3. Create virtual environment and install Python dependencies
echo "Configuring Python virtual environment in ${INSTALL_DIR}/.venv..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Execute setup.py (interactive or automated onboarding wizard)
echo "Running OmniPost setup wizard..."
python setup.py "$@"

# 5. Install and enable systemd service
echo "Installing systemd service omnipost.service..."
cp systemd/omnipost.service /etc/systemd/system/omnipost.service

systemctl daemon-reload
systemctl enable omnipost.service
systemctl restart omnipost.service

echo "========================================="
echo " OmniPost VPS deployment complete!"
echo " Service status:"
systemctl status omnipost.service --no-pager || true
echo "========================================="
