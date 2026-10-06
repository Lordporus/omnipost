# Task 4 Brief: Windows Task Scheduler Integration & Service Runner

## Goal
Implement `scripts/setup_scheduler.ps1`, `scripts/daemon.py`, and update `scripts/autoposter.py`.
Provides automated execution:
1. `scripts/daemon.py`: Standalone Python background loop that monitors due slots every 5 minutes and runs the pipeline at 11:00 AM.
2. `scripts/setup_scheduler.ps1`: One-click PowerShell script registering Windows Scheduled Tasks (`OmniPost-DailyPipeline` at 11:00 AM, `OmniPost-AutoposterGate` every 10 mins).
3. `scripts/autoposter.py`: Update to auto-trigger pipeline generation if slots have empty draft text instead of skipping.

## Files
- Create: `scripts/daemon.py`
- Create: `scripts/setup_scheduler.ps1`
- Modify: `scripts/autoposter.py`

## Interfaces
- Consumes: `scripts/pipeline.py`, `scripts/autoposter.py`, `scripts/browser_daemon.py`
- Produces: Persistent unattended execution without manual CLI intervention

## Steps to Execute
1. Implement `scripts/daemon.py`:
```python
"""Standalone Unattended Daemon for OmniPost.

Runs continuously in the background:
- Verifies Edge browser session is active.
- Triggers the daily pipeline at 11:00 AM (or if today's plan has empty text).
- Runs autoposter check every 5 minutes to publish slots when due.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def main():
    print("[DAEMON] OmniPost Autonomous Syndicate Daemon started.")
    print("[DAEMON] Press Ctrl+C to terminate.")

    last_pipeline_date = ""

    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 1. Run pipeline if it's 11:00+ or plan is missing
        plan_path = ROOT / "drafts" / f"{today}.json"
        should_run_pipeline = (today != last_pipeline_date and now.hour >= 11) or not plan_path.exists()
        if should_run_pipeline:
            print(f"[{now.strftime('%H:%M:%S')}] [DAEMON] Triggering daily pipeline...")
            subprocess.run([sys.executable, str(SCRIPTS / "pipeline.py")], cwd=str(ROOT))
            last_pipeline_date = today

        # 2. Run autoposter tick
        try:
            subprocess.run([sys.executable, str(SCRIPTS / "autoposter.py")], cwd=str(ROOT))
        except Exception as exc:
            print(f"[DAEMON] Autoposter error: {exc}", file=sys.stderr)

        # 3. Sleep 300 seconds (5 minutes)
        time.sleep(300)


if __name__ == "__main__":
    main()
```
2. Implement `scripts/setup_scheduler.ps1`:
```powershell
# scripts/setup_scheduler.ps1
# Sets up Windows Scheduled Tasks for 100% unattended OmniPost operation.
# Run from an elevated or standard PowerShell console.

$PythonExe = (Get-Command python).Source
$RootPath = (Get-Item $PSScriptRoot).Parent.FullName
$PipelineScript = Join-Path $RootPath "scripts\pipeline.py"
$AutoposterScript = Join-Path $RootPath "scripts\autoposter.py"

Write-Host "Configuring OmniPost Scheduled Tasks..." -ForegroundColor Cyan
Write-Host "Python: $PythonExe"
Write-Host "Root: $RootPath"

# 1. Daily Pipeline Task (Runs daily at 11:00 AM)
$DailyAction = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$PipelineScript`"" -WorkingDirectory $RootPath
$DailyTrigger = New-ScheduledTaskTrigger -Daily -At 11:00AM
Register-ScheduledTask -TaskName "OmniPost-DailyPipeline" -Action $DailyAction -Trigger $DailyTrigger -Description "Generates daily multi-platform content and media for OmniPost" -Force

# 2. Autoposter Gatekeeper Task (Runs every 10 minutes)
$GateAction = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$AutoposterScript`"" -WorkingDirectory $RootPath
$GateTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration ([TimeSpan]::MaxValue)
Register-ScheduledTask -TaskName "OmniPost-AutoposterGate" -Action $GateAction -Trigger $GateTrigger -Description "Monitors due slots and publishes across X, Bluesky, LinkedIn, and Threads" -Force

Write-Host "Scheduled tasks registered successfully!" -ForegroundColor Green
Write-Host "1. OmniPost-DailyPipeline (Daily at 11:00 AM)"
Write-Host "2. OmniPost-AutoposterGate (Every 10 minutes)"
```
3. Update `scripts/autoposter.py` so that if `due_item.get("text")` is empty, it runs `pipeline.run_daily_pipeline()` to auto-populate the plan on the fly.
4. Verify by running `python scripts/autoposter.py --dry-run`.
5. Commit:
`git add scripts/daemon.py scripts/setup_scheduler.ps1 scripts/autoposter.py`
`git commit -m "feat(scheduler): add Windows Task Scheduler installer and autonomous daemon"`
6. Write report to `.superpowers/sdd/production-schedule-plan/task-4-report.md`.
