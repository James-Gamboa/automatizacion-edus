#!/usr/bin/env bash
# Watchdog wrapper — only runs inside Costa Rica 5:00–8:00 window (guide Phase 5).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Prefer project venv when present (avoids wrong system Python / Pillow breaks)
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
: "${PYTHON_BIN:?python3 / .venv not found}"

# Load .env if present (export KEY=VAL lines only — safer than source for passwords)
if [[ -f .env ]]; then
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    [[ "${line}" != *=* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    val="${val#"${val%%[![:space:]]*}"}"
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    export "${key}=${val}"
  done < .env
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
# || true: intentional for cron (no_slots / outside window must not mail noise)
"${PYTHON_BIN}" scripts/edus_cli.py monitor --specialty "${SPECIALTY}" --force \
  2>> logs/edus_errors.log || true
