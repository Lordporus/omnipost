# Task 6 Brief: VPS Linux Deployment & Non-Blocking Xvfb Lifecycle

## Goal
Implement `systemd/omnipost.service`, `scripts/run_vps.sh`, `scripts/deploy_vps.sh`, and `tests/test_vps_deployment.py`.
Provides automated 1-click VPS provisioning for Ubuntu/Debian and production systemd service orchestration with a non-blocking Xvfb lifecycle.

## Files
- **Create:** `systemd/omnipost.service`
- **Create:** `scripts/run_vps.sh`
- **Create:** `scripts/deploy_vps.sh`
- **Create:** `tests/test_vps_deployment.py`

## Specifications

### 1. `scripts/run_vps.sh`
- Checks whether Xvfb display `:99` is active.
- If not running, launches `Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &` in the background (non-blocking).
- Sleeps 1 second for socket readiness.
- Runs `exec python scripts/daemon.py "$@"`.

### 2. `systemd/omnipost.service`
- `WorkingDirectory=/opt/omnipost`
- `EnvironmentFile=/opt/omnipost/.env`
- `Environment=DISPLAY=:99`
- `Environment=IS_LINUX=1`
- `ExecStart=/bin/bash /opt/omnipost/scripts/run_vps.sh`
- `Restart=always`
- `RestartSec=15`

### 3. `scripts/deploy_vps.sh`
- Installs dependencies: `python3`, `python3-pip`, `python3-venv`, `chromium`, `xvfb`, `fonts-liberation`, `fonts-noto-color-emoji`, `curl`, `git`.
- Clones / sets up `/opt/omnipost`.
- Creates virtual environment `.venv` and installs `requirements.txt`.
- Runs `python setup.py`.
- Installs and starts systemd service `omnipost.service`.

## TDD Steps
1. Write `tests/test_vps_deployment.py` verifying:
   - `scripts/run_vps.sh` exists, starts Xvfb in background (`&`), and executes daemon.
   - `systemd/omnipost.service` exists, contains required configuration, and uses `run_vps.sh`.
   - `scripts/deploy_vps.sh` exists, installs required packages, sets up `.venv`, and manages systemd.
2. Run test to verify it fails:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_vps_deployment.py`
3. Implement `scripts/run_vps.sh`, `systemd/omnipost.service`, `scripts/deploy_vps.sh`.
4. Run test to verify it passes:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_vps_deployment.py`
5. Commit:
   `git add systemd/omnipost.service scripts/run_vps.sh scripts/deploy_vps.sh tests/test_vps_deployment.py`
   `git commit -m "feat(vps): implement headless VPS deployment, systemd service, and non-blocking Xvfb runner"`
6. Write report to `.superpowers/sdd/onboarding-deployment-execution-plan/task-6-report.md`.
