#Requires -Version 5.1
param(
    [ValidateSet("medicina_general", "odontologia")]
    [string]$Specialty = "medicina_general",
    [switch]$Force,
    # Default behavior is check-only unless -AutoBook is set
    [switch]$CheckOnly,
    [switch]$AutoBook
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Load .env into process environment (simple parser)
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

$useCheckOnly = -not $AutoBook
$argsList = @("scripts\edus_cli.py", "monitor", "--specialty", $Specialty)
if ($Force) { $argsList += "--force" }
if ($useCheckOnly) { $argsList += "--check-only" }

$output = & $Python @argsList 2>&1 | Out-String
$code = $LASTEXITCODE
if ($output.Trim()) {
    Write-Host $output
    # Windows toast when cupos appear (check-only / booked)
    if ($output -match "hay cupos|slots_available|Booked|booked") {
        try {
            Add-Type -AssemblyName System.Windows.Forms | Out-Null
            Add-Type -AssemblyName System.Drawing | Out-Null
            $notify = New-Object System.Windows.Forms.NotifyIcon
            $notify.Icon = [System.Drawing.SystemIcons]::Information
            $notify.Visible = $true
            $notify.BalloonTipTitle = "EDUS Citas"
            $trimmed = $output.Trim() -replace "`r", ""
            $tip = $trimmed.Substring(0, [Math]::Min(200, $trimmed.Length))
            $notify.BalloonTipText = $tip
            $notify.ShowBalloonTip(8000)
            Start-Sleep -Seconds 2
            $notify.Dispose()
        } catch {
            # Toast is best-effort
        }
    }
}
exit $code
