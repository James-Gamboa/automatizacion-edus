"""Hermes plugin: intercept EDUS reserve taps and skip the LLM."""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path

FAST_INTENT_RE = re.compile(
    r"reserva\s+esta\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}"
    r"|reserva(?:me)?\s+el\s+primero"
    r"|(?:escogeme|escoge|elige|el\s+de\s+las)\s+\d{1,2}:\d{2}"
    r"|s[aá]came\s+una\s+cita"
    r"|reserv(?:a|ame)\s+una\s+cita"
    r"|\bok,?\s*reserva",
    re.IGNORECASE,
)


def _project_root() -> Path:
    env = os.environ.get("EDUS_PROJECT_ROOT", "").strip()
    if env:
        return Path(env)
    local = Path.home() / "automatizacion-edus"
    if local.is_dir():
        return local
    return local


def _python(root: Path) -> Path:
    win = root / ".venv" / "Scripts" / "python.exe"
    unix = root / ".venv" / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    raise FileNotFoundError(f"Project venv Python not found under {root}")


def _run_fast_reserve(message: str) -> None:
    root = _project_root()
    script = root / "scripts" / "edus_fast_reserve.py"
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    subprocess.run(
        [str(_python(root)), "-I", str(script), "--message", message],
        cwd=str(root),
        env=env,
        timeout=240,
        check=False,
    )


def intercept_reserve(event, **kwargs):
    text = getattr(event, "text", None) or ""
    if not FAST_INTENT_RE.search(text):
        return None
    threading.Thread(target=_run_fast_reserve, args=(text,), daemon=True).start()
    return {"action": "skip", "reason": "edus-fast-book"}


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", intercept_reserve)
