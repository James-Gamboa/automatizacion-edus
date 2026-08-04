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

# Optional OCR (Debian/Ubuntu)
if command -v apt-get >/dev/null 2>&1; then
  if ! command -v tesseract >/dev/null 2>&1; then
    echo "Tip: sudo apt-get install -y tesseract-ocr tesseract-ocr-spa"
  fi
fi

python3 scripts/edus_cli.py validate
echo "Done."
