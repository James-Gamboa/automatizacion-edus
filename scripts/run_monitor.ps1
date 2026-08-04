#Requires -Version 5.1
param(
    [ValidateSet("medicina_general", "odontologia")]
    [string]$Specialty = "medicina_general",
    [switch]$Force
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

$argsList = @("scripts\edus_cli.py", "monitor", "--specialty", $Specialty)
if ($Force) { $argsList += "--force" }

& python @argsList
exit $LASTEXITCODE
