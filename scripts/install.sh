#!/usr/bin/env bash
# Install Python deps + Playwright Chromium for EDUS Citas automation.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== EDUS Citas install =="
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill EDUS_CEDULA and EDUS_CLAVE."
fi

# Optional OCR tips
if ! command -v tesseract >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Tip (macOS): brew install tesseract tesseract-lang"
  elif command -v apt-get >/dev/null 2>&1; then
    echo "Tip (Debian/Ubuntu): sudo apt-get install -y tesseract-ocr tesseract-ocr-spa"
  else
    echo "Tip: install Tesseract OCR and ensure 'tesseract' is on PATH."
  fi
fi

python3 scripts/edus_cli.py validate
echo "Done. Next: edit .env, then:"
echo "  python3 scripts/edus_cli.py book --specialty medicina_general --force --dry-run"
