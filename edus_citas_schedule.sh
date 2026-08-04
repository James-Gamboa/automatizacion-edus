#!/usr/bin/env bash
# Watchdog wrapper — only runs inside Costa Rica 5:00–8:00 window (guide Phase 5).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${EDUS_CEDULA:?EDUS_CEDULA is required}"
: "${EDUS_CLAVE:?EDUS_CLAVE is required}"

SPECIALTY="${1:-medicina_general}"
FORCE="${2:-}"

HOUR="$(TZ='America/Costa_Rica' date +%H)"
if [[ "${FORCE}" != "--force" ]]; then
  if [[ "${HOUR}" -lt 5 || "${HOUR}" -ge 8 ]]; then
    exit 0
  fi
fi

mkdir -p logs
# stderr to log; keep cron quiet unless actionable stdout from watchdog
python3 scripts/edus_cli.py monitor --specialty "${SPECIALTY}" --force \
  2>> logs/edus_errors.log || true
