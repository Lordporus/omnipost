# Task 5 Brief: Containerized Stack (Docker, Compose & Entrypoint Directory Guard)

## Goal
Implement `Dockerfile`, `docker-compose.yml`, `scripts/docker-entrypoint.sh`, update `requirements.txt`, and write tests in `tests/test_docker_config.py`.
Provides a production-grade isolated container stack with headless Chromium, Xvfb virtual framebuffer, named volumes, healthchecks, and the critical host bind-mount directory collision guard.

## Files
- **Create:** `Dockerfile`
- **Create:** `docker-compose.yml`
- **Create:** `scripts/docker-entrypoint.sh`
- **Modify:** `requirements.txt` (ensure PyYAML or required packages included if needed)
- **Create:** `tests/test_docker_config.py`

## Specifications

### 1. `Dockerfile`
- Base: `python:3.12-slim-bookworm`
- Environment variables: `DEBIAN_FRONTEND=noninteractive`, `PYTHONUNBUFFERED=1`, `DISPLAY=:99`, `IS_DOCKER=1`
- Installs `chromium`, `chromium-driver`, `xvfb`, `fonts-liberation`, `fonts-dejavu-core`, `procps`, `curl`
- Installs `requirements.txt`
- Copies entrypoint script to `/usr/local/bin/docker-entrypoint.sh` with `chmod +x`
- Entrypoint: `docker-entrypoint.sh`
- Default CMD: `["python", "scripts/daemon.py"]`

### 2. `scripts/docker-entrypoint.sh`
- **Refinement 1 Guard:** Checks if `/app/state.json` or `/app/.env` is a directory. If true, prints actionable fatal message and exits with code 1.
- Starts virtual framebuffer: `Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &`
- Executes command: `exec "$@"`

### 3. `docker-compose.yml`
- Service `omnipost` with `build: .`, `container_name: omnipost-engine`, `restart: unless-stopped`
- `env_file: [.env]`
- Persistent volumes: `browser_profile:/app/browser-data`, `./config.json:/app/config.json:ro`, `./state.json:/app/state.json`, `./drafts:/app/drafts`, `./swipe:/app/swipe`, `./scratch:/app/scratch`
- Environment: `DISPLAY=:99`, `IS_DOCKER=1`, `BROWSER_PROFILE=/app/browser-data`, `CHROME_PATH=/usr/bin/chromium`
- Healthcheck: `["CMD", "python", "scripts/doctor.py", "--healthcheck"]`
- Named volume: `browser_profile: name: omnipost_browser_data`

## TDD Steps
1. Write `tests/test_docker_config.py` testing:
   - `Dockerfile` exists and has proper base image, entrypoint, and environment variables.
   - `scripts/docker-entrypoint.sh` exists, starts Xvfb, and contains the directory collision guard for `state.json` and `.env`.
   - `docker-compose.yml` exists, contains volume mappings, healthcheck, and restart policy.
2. Run test to verify it fails:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_docker_config.py`
3. Implement `Dockerfile`, `docker-compose.yml`, `scripts/docker-entrypoint.sh`.
4. Run test to verify it passes:
   `C:\Users\Sachin\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_docker_config.py`
5. Commit:
   `git add Dockerfile docker-compose.yml scripts/docker-entrypoint.sh tests/test_docker_config.py requirements.txt`
   `git commit -m "feat(docker): implement container image, compose stack, and entrypoint directory guard"`
6. Write report to `.superpowers/sdd/onboarding-deployment-execution-plan/task-5-report.md`.
