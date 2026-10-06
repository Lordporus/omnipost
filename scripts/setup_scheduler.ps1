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
