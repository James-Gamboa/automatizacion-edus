#Requires -Version 5.1
<#
.SYNOPSIS
  Optional Windows Task Scheduler for EDUS (morning window ONLY).
  Prefer Hermes cron + Telegram (see MONITOR.md). This is a local backup.
.NOTES
  Runs every 5 minutes from 05:00 to 08:00 local time ONLY — not all day.
#>
param(
    [ValidateSet("medicina_general", "odontologia")]
    [string]$Specialty = "medicina_general",
    [string]$TaskName = "EDUS-Citas-Monitor",
    [switch]$AutoBook,
    [string]$StartTime = "05:00",
    # How long to keep repeating after StartTime (3h => 05:00–08:00)
    [string]$Duration = "03:00"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Wrapper = Join-Path $Root "scripts\run_monitor.ps1"

if (-not (Test-Path $Wrapper)) {
    Write-Error "Missing $Wrapper"
}

if ($AutoBook) {
    $modeArgs = "-Specialty $Specialty -AutoBook"
} else {
    $modeArgs = "-Specialty $Specialty -CheckOnly"
}

# Hidden PowerShell — only during morning window (NOT all-day every 5m)
$tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Wrapper`" $modeArgs"

# Remove old all-day task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# DAILY at 05:00, repeat every 5 minutes for 3 hours → stops at 08:00
$create = schtasks.exe /Create /F /TN $TaskName /TR $tr /SC DAILY /ST $StartTime /RI 5 /DU $Duration
if ($LASTEXITCODE -ne 0) {
    Write-Error "schtasks failed: $create"
}

Write-Host "Scheduled task '$TaskName' registered." -ForegroundColor Green
Write-Host "Window: daily $StartTime for $Duration (every 5 min). Does NOT run after that."
if ($AutoBook) {
    Write-Host "Mode: AUTO-BOOK when slots appear."
} else {
    Write-Host "Mode: CHECK-ONLY - alert when cupos appear; you confirm before booking."
}
Write-Host "Prefer Hermes Telegram cron instead if you already use it (MONITOR.md)."
Write-Host "Remove later: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
