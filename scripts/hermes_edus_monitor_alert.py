"""Hermes no-agent cron script: alert Telegram when EDUS has cupos.

Install to Hermes scripts dir (Windows often):
  %LOCALAPPDATA%\\hermes\\scripts\\edus_monitor_alert.py

Then:
  hermes cron create "*/5 5-7 * * *" --no-agent --script edus_monitor_alert.py --deliver telegram --name edus-cupos

Rules (Hermes):
  - Empty stdout  → silent (no Telegram message)
  - Non-empty stdout → delivered to Telegram verbatim
  - Uses PROJECT venv Python with env cleaned (Hermes PYTHONPATH breaks Pillow)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SPECIALTY = os.environ.get("EDUS_MONITOR_SPECIALTY", "medicina_general")


def _project_root() -> Path:
    env = os.environ.get("EDUS_PROJECT_ROOT", "").strip()
    if env:
        return Path(env)
    candidate = Path.home() / "automatizacion-edus"
    if candidate.is_dir():
        return candidate
    raise SystemExit(
        "Set EDUS_PROJECT_ROOT to your clone path "
        "(or put the repo at ~/automatizacion-edus)."
    )


def _python(root: Path) -> Path:
    win = root / ".venv" / "Scripts" / "python.exe"
    unix = root / ".venv" / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    raise SystemExit(f"Project venv Python not found under {root}")


def _clean_env() -> dict[str, str]:
    """Hermes injects PYTHONPATH to its venv; that breaks project Pillow/_imaging."""
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def main() -> int:
    # Extra guard: silent outside 05:00–07:59 America/Costa_Rica
    try:
        from datetime import datetime, timedelta, timezone

        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo("America/Costa_Rica")
        except Exception:
            tz = timezone(timedelta(hours=-6))
        hour = datetime.now(tz).hour
        if hour < 5 or hour >= 8:
            return 0
    except Exception:
        pass

    root = _project_root()
    if not root.is_dir():
        print(f"EDUS project not found: {root}", file=sys.stderr)
        return 1

    py = _python(root)
    cli = root / "scripts" / "edus_cli.py"
    if not cli.is_file():
        print(f"Missing CLI: {cli}", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [str(py), "-I", str(cli), "monitor", "--specialty", SPECIALTY, "--check-only"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_clean_env(),
    )

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    if proc.returncode != 0:
        print(out or err or f"edus monitor failed (exit {proc.returncode})")
        return proc.returncode

    if out:
        print(out)
        if "hay cupos" in out.lower() or "slots_available" in out:
            print()
            print("Responde: ok, reservame el primero")
            print("O: ok, escogeme el de las HH:MM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
