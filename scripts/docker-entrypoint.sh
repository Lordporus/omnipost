#!/bin/bash
set -e

# Refinement 1 Guard: Prevent fatal crash caused by Docker auto-creating directories
# when host bind-mounted files do not exist prior to container start.
if [ -d "/app/state.json" ]; then
    echo "FATAL: /app/state.json is a directory! Docker created a directory because state.json was missing on the host before bind mount." >&2
    echo "Action required: Run 'rm -rf state.json && touch state.json' on host, or run 'python scripts/doctor.py' before launching Docker." >&2
    exit 1
fi

if [ -d "/app/.env" ]; then
    echo "FATAL: /app/.env is a directory! Docker created a directory because .env was missing on the host before bind mount." >&2
    echo "Action required: Run 'rm -rf .env && cp .env.example .env' on host before launching Docker." >&2
    exit 1
fi

# Start virtual framebuffer display for headless browser automation
echo "Starting virtual display Xvfb on :99..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &

# Brief pause to allow Xvfb socket initialization
sleep 1

# Execute container CMD
exec "$@"
