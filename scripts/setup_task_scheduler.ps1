#Requires -Version 5.1
<#
.SYNOPSIS
  Registers a Windows Task Scheduler job for EDUS monitoring (every 5 minutes, 5–7 Costa Rica).
.PARAMETER Specialty
  medicina_general or odontologia
.PARAMETER TaskName
  Scheduled task name
#>
param(
    [ValidateSet("medicina_general", "odontologia")]
    [string]$Specialty = "medicina_general",
    [string]$TaskName = "EDUS-Citas-Monitor"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source
$Cli = Join-Path $Root "scripts\edus_cli.py"
$Wrapper = Join-Path $Root "scripts\run_monitor.ps1"

if (-not (Test-Path $Wrapper)) {
    Write-Error "Missing $Wrapper"
}

# Task runs every 5 minutes daily; the Python watchdog enforces CR 5–8 window.
$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Wrapper`" -Specialty $Specialty"

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "Scheduled task '$TaskName' registered." -ForegroundColor Green
Write-Host "Ensure .env has EDUS_CEDULA / EDUS_CLAVE. Watchdog is silent when no slots."
Write-Host "Manual test: powershell -File `"$Wrapper`" -Specialty $Specialty -Force"
