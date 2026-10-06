"""Tests for Dockerfile, docker-compose.yml, and scripts/docker-entrypoint.sh."""
import os
import re
from pathlib import Path
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_exists_and_valid():
    """Verify Dockerfile exists and meets production specifications."""
    dockerfile_path = ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile does not exist at project root"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Base image: python:3.12-slim or python:3.12-slim-bookworm
    assert re.search(r"FROM\s+python:3\.12-slim(-bookworm)?", content, re.IGNORECASE), (
        "Dockerfile must use Python 3.12-slim base image"
    )

    # Required packages
    required_packages = [
        "chromium",
        "chromium-driver",
        "xvfb",
        "fonts-liberation",
        "fonts-dejavu-core",
        "procps",
        "curl",
    ]
    for pkg in required_packages:
        assert pkg in content, f"Dockerfile must install package '{pkg}'"

    # Environment variables
    assert "PYTHONUNBUFFERED=1" in content or "ENV PYTHONUNBUFFERED=1" in content, (
        "Dockerfile must set PYTHONUNBUFFERED=1"
    )
    assert "DISPLAY=:99" in content, "Dockerfile must set DISPLAY=:99"
    assert "IS_DOCKER=1" in content, "Dockerfile must set IS_DOCKER=1"

    # requirements.txt install
    assert "requirements.txt" in content, "Dockerfile must copy and install requirements.txt"
    assert "pip install" in content, "Dockerfile must run pip install"

    # Entrypoint script copied and set
    assert "docker-entrypoint.sh" in content, "Dockerfile must reference docker-entrypoint.sh"
    assert "ENTRYPOINT" in content, "Dockerfile must configure ENTRYPOINT"

    # Default CMD
    assert "daemon.py" in content, "Dockerfile must set default CMD to run scripts/daemon.py"


def test_docker_entrypoint_script():
    """Verify scripts/docker-entrypoint.sh exists, is executable, and contains collision guard and Xvfb."""
    entrypoint_path = ROOT / "scripts" / "docker-entrypoint.sh"
    assert entrypoint_path.exists(), "scripts/docker-entrypoint.sh does not exist"

    content = entrypoint_path.read_text(encoding="utf-8")

    # Shebang check
    assert (
        content.startswith("#!/bin/sh")
        or content.startswith("#!/bin/bash")
        or content.startswith("#!/usr/bin/env bash")
        or content.startswith("#!/usr/bin/env sh")
    ), "docker-entrypoint.sh must start with a valid shell shebang"

    # Refinement 1 Guard: Directory collision check for /app/state.json
    assert "/app/state.json" in content, "Entrypoint must check /app/state.json"
    assert "-d /app/state.json" in content or '-d "/app/state.json"' in content, (
        "Entrypoint must test if /app/state.json is a directory (-d)"
    )

    # Refinement 1 Guard: Directory collision check for /app/.env
    assert "/app/.env" in content, "Entrypoint must check /app/.env"
    assert "-d /app/.env" in content or '-d "/app/.env"' in content, (
        "Entrypoint must test if /app/.env is a directory (-d)"
    )

    # Exits with code 1 if directory collision occurs
    assert "exit 1" in content, "Entrypoint must exit with code 1 on directory collision"
    assert "FATAL" in content, "Entrypoint must output FATAL message when directory collision occurs"

    # Actionable guidance
    assert "state.json" in content and ("touch" in content or "doctor.py" in content), (
        "Entrypoint must guide user on how to fix state.json directory collision"
    )
    assert ".env" in content and (".env.example" in content or "touch" in content), (
        "Entrypoint must guide user on how to fix .env directory collision"
    )

    # Starts Xvfb virtual framebuffer
    assert "Xvfb :99" in content, "Entrypoint must start Xvfb on display :99"
    assert "1920x1080x24" in content, "Entrypoint must configure screen 1920x1080x24"

    # Executes command
    assert 'exec "$@"' in content, "Entrypoint must hand over control with exec \"$@\""


def test_docker_compose_config():
    """Verify docker-compose.yml configuration, services, volumes, and healthcheck."""
    compose_path = ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml does not exist at project root"

    content = compose_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert "services" in data, "docker-compose.yml must define services"
    assert "omnipost" in data["services"], "docker-compose.yml must define omnipost service"

    omnipost = data["services"]["omnipost"]

    # Container name and restart policy
    assert omnipost.get("container_name") == "omnipost-engine"
    assert omnipost.get("restart") == "unless-stopped"

    # env_file
    env_file = omnipost.get("env_file", [])
    if isinstance(env_file, str):
        env_file = [env_file]
    assert ".env" in env_file or "./.env" in env_file, (
        "omnipost service must include .env in env_file"
    )

    # Environment variables
    env_vars = omnipost.get("environment", {})
    if isinstance(env_vars, list):
        env_dict = {}
        for item in env_vars:
            if "=" in item:
                k, v = item.split("=", 1)
                env_dict[k] = v
        env_vars = env_dict

    assert env_vars.get("DISPLAY") == ":99"
    assert str(env_vars.get("IS_DOCKER")) == "1"
    assert env_vars.get("BROWSER_PROFILE") == "/app/browser-data"
    assert env_vars.get("CHROME_PATH") == "/usr/bin/chromium"

    # Volume mappings
    volumes = omnipost.get("volumes", [])
    required_volumes = [
        "browser_profile:/app/browser-data",
        "./config.json:/app/config.json:ro",
        "./state.json:/app/state.json",
        "./drafts:/app/drafts",
        "./swipe:/app/swipe",
        "./scratch:/app/scratch",
    ]
    for req in required_volumes:
        assert req in volumes, f"omnipost service must mount volume '{req}'"

    # Named volume definition
    assert "volumes" in data, "docker-compose.yml must define top-level volumes"
    assert "browser_profile" in data["volumes"], (
        "docker-compose.yml must define top-level named volume 'browser_profile'"
    )
    bp_vol = data["volumes"]["browser_profile"] or {}
    assert bp_vol.get("name") == "omnipost_browser_data", (
        "browser_profile named volume must have name 'omnipost_browser_data'"
    )

    # Healthcheck
    assert "healthcheck" in omnipost, "omnipost service must define a healthcheck"
    hc = omnipost["healthcheck"]
    hc_test = hc.get("test", [])
    if isinstance(hc_test, list):
        hc_test_str = " ".join(hc_test)
    else:
        hc_test_str = str(hc_test)
    assert "scripts/doctor.py" in hc_test_str
    assert "--healthcheck" in hc_test_str
