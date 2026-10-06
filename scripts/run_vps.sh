#!/bin/bash
set -e

# OmniPost VPS Headless Runner with non-blocking Xvfb lifecycle

export DISPLAY=:99
export IS_LINUX=1

# Check whether Xvfb display :99 is active
if ! pgrep -f "Xvfb :99" > /dev/null 2>&1 && [ ! -e "/tmp/.X11-unix/X99" ] && [ ! -e "/tmp/.X99-lock" ]; then
    echo "Starting virtual display Xvfb on :99 in background..."
    Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
    # Socket readiness check / wait
    sleep 1
else
    echo "Xvfb display :99 is already active."
fi

# Activate virtualenv if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "/opt/omnipost/.venv/bin/activate" ]; then
    source /opt/omnipost/.venv/bin/activate
fi

# Execute daemon passing all incoming command line arguments
exec python scripts/daemon.py "$@"
