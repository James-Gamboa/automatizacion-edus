#Requires -Version 5.1
<#
.SYNOPSIS
  Installs Python dependencies and Playwright Chromium for EDUS Citas automation.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== EDUS Citas install ==" -ForegroundColor Cyan

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python not found on PATH. Install Python 3.10+ from https://www.python.org/"
}

Write-Host "Python: $(python --version)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — fill EDUS_CEDULA and EDUS_CLAVE." -ForegroundColor Yellow
}

Write-Host "Validating dependencies..."
python scripts/edus_cli.py validate

$tess = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $tess -and -not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) {
    Write-Host "Tesseract OCR is required for CAPTCHA. Install with:" -ForegroundColor Yellow
    Write-Host "  winget install --id UB-Mannheim.TesseractOCR -e"
    Write-Host "Then set TESSERACT_CMD in .env if it is not on PATH."
}

Write-Host "Done. Next: edit .env, then run: python scripts/edus_cli.py book --specialty medicina_general --force --dry-run" -ForegroundColor Green
