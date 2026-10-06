"""Tests for VPS Linux deployment, systemd service, and run_vps.sh script."""
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_run_vps_script_exists_and_valid():
    """Verify scripts/run_vps.sh exists, contains non-blocking Xvfb startup, socket check, and daemon execution."""
    run_vps_path = ROOT / "scripts" / "run_vps.sh"
    assert run_vps_path.exists(), "scripts/run_vps.sh does not exist"

    content = run_vps_path.read_text(encoding="utf-8")

    # Shebang check
    assert (
        content.startswith("#!/bin/bash")
        or content.startswith("#!/bin/sh")
        or content.startswith("#!/usr/bin/env bash")
    ), "run_vps.sh must start with a valid bash shebang"

    # Display :99 checks
    assert ":99" in content, "run_vps.sh must reference display :99"
    assert "Xvfb" in content, "run_vps.sh must manage Xvfb"

    # Non-blocking Xvfb launch (&)
    assert re.search(r"Xvfb\s+:99.*?&\s*$", content, re.MULTILINE), (
        "run_vps.sh must start Xvfb in the background with '&' (non-blocking)"
    )

    # Resolution configuration
    assert "1920x1080x24" in content, "run_vps.sh must configure Xvfb with 1920x1080x24"

    # Socket readiness check / wait
    assert "sleep" in content or "/tmp/.X11-unix/X99" in content or ".X99-lock" in content, (
        "run_vps.sh must include a socket readiness wait or check"
    )

    # Environment variables
    assert "DISPLAY=:99" in content, "run_vps.sh must set DISPLAY=:99"
    assert "IS_LINUX=1" in content, "run_vps.sh must set IS_LINUX=1"

    # Executes daemon with arguments
    assert re.search(r'python(3)?\s+scripts/daemon\.py\s+"\$@"', content), (
        'run_vps.sh must execute python scripts/daemon.py "$@"'
    )


def test_systemd_omnipost_service_exists_and_valid():
    """Verify systemd/omnipost.service meets production specifications."""
    service_path = ROOT / "systemd" / "omnipost.service"
    assert service_path.exists(), "systemd/omnipost.service does not exist"

    content = service_path.read_text(encoding="utf-8")

    # Unit section
    assert "[Unit]" in content, "omnipost.service must contain [Unit] section"
    assert "[Service]" in content, "omnipost.service must contain [Service] section"
    assert "[Install]" in content, "omnipost.service must contain [Install] section"

    # WorkingDirectory
    assert "WorkingDirectory=/opt/omnipost" in content, (
        "omnipost.service must set WorkingDirectory=/opt/omnipost"
    )

    # Environment and EnvironmentFile
    assert "EnvironmentFile=/opt/omnipost/.env" in content or "EnvironmentFile=-/opt/omnipost/.env" in content, (
        "omnipost.service must specify EnvironmentFile=/opt/omnipost/.env"
    )
    assert "Environment=DISPLAY=:99" in content or "DISPLAY=:99" in content, (
        "omnipost.service must specify DISPLAY=:99"
    )
    assert "Environment=IS_LINUX=1" in content or "IS_LINUX=1" in content, (
        "omnipost.service must specify IS_LINUX=1"
    )

    # ExecStart points to run_vps.sh
    assert re.search(r"ExecStart=.*run_vps\.sh", content), (
        "omnipost.service ExecStart must execute run_vps.sh"
    )

    # Avoid blocking ExecStartPre with Xvfb
    assert "ExecStartPre=" not in content or "Xvfb" not in content.split("ExecStartPre=")[1].split("\n")[0], (
        "omnipost.service must not have blocking ExecStartPre running Xvfb"
    )

    # Restart policy
    assert "Restart=always" in content, "omnipost.service must have Restart=always"
    assert "RestartSec=" in content, "omnipost.service must configure RestartSec"


def test_deploy_vps_script_exists_and_valid():
    """Verify scripts/deploy_vps.sh provisions packages, creates .venv, runs setup, and installs systemd."""
    deploy_path = ROOT / "scripts" / "deploy_vps.sh"
    assert deploy_path.exists(), "scripts/deploy_vps.sh does not exist"

    content = deploy_path.read_text(encoding="utf-8")

    # Shebang check
    assert (
        content.startswith("#!/bin/bash")
        or content.startswith("#!/bin/sh")
        or content.startswith("#!/usr/bin/env bash")
    ), "deploy_vps.sh must start with a valid bash shebang"

    # Required package dependencies
    required_packages = [
        "python3",
        "python3-venv",
        "chromium",
        "xvfb",
        "fonts-liberation",
        "fonts-noto-color-emoji",
    ]
    for pkg in required_packages:
        assert pkg in content, f"deploy_vps.sh must install or reference package '{pkg}'"

    # Virtual environment setup
    assert ".venv" in content or "venv" in content, "deploy_vps.sh must set up a virtual environment"
    assert "requirements.txt" in content, "deploy_vps.sh must install requirements.txt"

    # setup.py execution
    assert "setup.py" in content, "deploy_vps.sh must execute setup.py"

    # systemd installation
    assert "omnipost.service" in content, "deploy_vps.sh must configure omnipost.service"
    assert "systemctl" in content, "deploy_vps.sh must use systemctl to enable/start the service"
