"""Parse Telegram reserve taps and run book without the LLM."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from edus.config import LAST_RESULT_PATH, ROOT_DIR
from edus.result_store import RunResult, load_result

RESERVA_ESTA_RE = re.compile(
    r"reserva\s+esta\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)
PRIMERO_RE = re.compile(
    r"reserva(?:me)?\s+el\s+primero",
    re.IGNORECASE,
)
HORA_PICK_RE = re.compile(
    r"(?:escogeme|escoge|elige|el\s+de\s+las)\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)
GENERIC_BOOK_RE = re.compile(
    r"s[aá]came\s+una\s+cita|reserv(?:a|ame)\s+una\s+cita",
    re.IGNORECASE,
)
FAST_INTENT_RE = re.compile(
    r"reserva\s+esta\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}"
    r"|reserva(?:me)?\s+el\s+primero"
    r"|(?:escogeme|escoge|elige|el\s+de\s+las)\s+\d{1,2}:\d{2}"
    r"|s[aá]came\s+una\s+cita"
    r"|reserv(?:a|ame)\s+una\s+cita"
    r"|\bok,?\s*reserva",
    re.IGNORECASE,
)

_SPECIALTY_LABELS = {
    "medicina general": "medicina_general",
    "medicina_general": "medicina_general",
    "odontologia": "odontologia",
    "odontología": "odontologia",
    "odonto": "odontologia",
}


def is_fast_reserve_message(text: str) -> bool:
    return bool(FAST_INTENT_RE.search(text or ""))


def _specialty_from_text(text: str, last: Optional[RunResult]) -> str:
    lowered = (text or "").lower()
    if "odonto" in lowered or "dental" in lowered:
        return "odontologia"
    if "medicina" in lowered:
        return "medicina_general"
    label = (last.specialty if last else "") or ""
    mapped = _SPECIALTY_LABELS.get(label.lower().strip())
    if mapped:
        return mapped
    return "medicina_general"


def _all_slots(last: Optional[RunResult]) -> list[dict[str, Any]]:
    if last is None:
        return []
    return list(last.slots_found or []) + list(last.slots_out_of_window or [])


def parse_reserve_intent(
    text: str,
    last: Optional[RunResult] = None,
) -> Optional[dict[str, Optional[str]]]:
    raw = (text or "").strip()
    if not raw:
        return None
    specialty = _specialty_from_text(raw, last)

    match = RESERVA_ESTA_RE.search(raw)
    if match:
        return {
            "fecha": match.group(1),
            "hora": match.group(2),
            "specialty": specialty,
        }

    hora_match = HORA_PICK_RE.search(raw)
    if hora_match:
        want = hora_match.group(1)
        for slot in _all_slots(last):
            if str(slot.get("hora") or "").startswith(want) or want in str(slot.get("hora") or ""):
                return {
                    "fecha": str(slot.get("fecha") or ""),
                    "hora": str(slot.get("hora") or want),
                    "specialty": specialty,
                }
        return {"fecha": None, "hora": want, "specialty": specialty}

    if re.search(r"^ok,?\s*reserva(?:me)?\s*$", raw, re.I):
        slots = _all_slots(last)
        if slots:
            first = slots[0]
            return {
                "fecha": str(first.get("fecha") or ""),
                "hora": str(first.get("hora") or ""),
                "specialty": specialty,
            }
        return {"fecha": None, "hora": None, "specialty": specialty}

    if PRIMERO_RE.search(raw) and not GENERIC_BOOK_RE.search(raw):
        slots = _all_slots(last)
        if slots:
            first = slots[0]
            return {
                "fecha": str(first.get("fecha") or ""),
                "hora": str(first.get("hora") or ""),
                "specialty": specialty,
            }

    if GENERIC_BOOK_RE.search(raw):
        return {"fecha": None, "hora": None, "specialty": specialty}

    return None


def project_python(root: Path = ROOT_DIR) -> Path:
    win = root / ".venv" / "Scripts" / "python.exe"
    unix = root / ".venv" / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    raise FileNotFoundError(f"Project venv Python not found under {root}")


def run_book_cli(
    *,
    specialty: str,
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
    root: Path = ROOT_DIR,
    timeout: int = 180,
) -> int:
    py = project_python(root)
    cli = root / "scripts" / "edus_cli.py"
    cmd = [
        str(py),
        "-I",
        str(cli),
        "book",
        "--specialty",
        specialty,
        "--force",
        "--any-time",
    ]
    if fecha:
        cmd.extend(["--fecha", fecha])
    if hora:
        cmd.extend(["--hora", hora])
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )
    return proc.returncode


def format_book_reply(result: Optional[RunResult]) -> str:
    if result is None:
        return "EDUS: no pude leer el resultado de la reserva."
    if result.status in {"booked", "booked_dry_run"}:
        slot = result.booked_slot or {}
        kind = "DRY-RUN" if result.status == "booked_dry_run" else "RESERVADA"
        return "\n".join(
            [
                f"EDUS - CITA {kind}",
                f"Especialidad: {result.specialty}",
                f"Fecha: {slot.get('fecha', '?')}",
                f"Hora: {slot.get('hora', '?')}",
            ]
        )
    if result.status == "no_slots":
        return f"EDUS: esa cita ya no estaba. {result.message}".strip()
    if result.status == "waf_rejected":
        return "EDUS bloqueo (WAF). Espera 15-60 min. No reintento."
    return f"EDUS: {result.status}. {result.message}".strip()


def acquire_lock(path: Path = ROOT_DIR / "data" / "fast_book.lock") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            age = __import__("time").time() - path.stat().st_mtime
            if age < 180:
                return False
        except OSError:
            return False
    path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock(path: Path = ROOT_DIR / "data" / "fast_book.lock") -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def last_result(path: Path = LAST_RESULT_PATH) -> Optional[RunResult]:
    return load_result(path)
