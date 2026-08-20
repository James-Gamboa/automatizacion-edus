"""Monitor pause + alert dedupe for Hermes cron."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from edus.config import DATA_DIR, LAST_RESULT_PATH
from edus.result_store import RunResult, load_result

PAUSE_PATH = DATA_DIR / "monitor_paused.json"
ALERTED_SLOTS_PATH = DATA_DIR / "last_alerted_slots.txt"


def _slots_fingerprint(slots: list[dict[str, Any]]) -> str:
    parts = sorted(
        f"{slot.get('fecha', '?')}|{slot.get('hora', '?')}"
        for slot in slots
    )
    raw = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def is_monitor_paused(path: Path = PAUSE_PATH) -> bool:
    return path.is_file()


def pause_monitor(
    *,
    reason: str = "booked",
    specialty: str = "",
    slot: Optional[dict[str, Any]] = None,
    path: Path = PAUSE_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "paused": True,
        "reason": reason,
        "specialty": specialty,
        "slot": slot or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resume_monitor(path: Path = PAUSE_PATH) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        ALERTED_SLOTS_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def pause_from_last_result(path: Path = LAST_RESULT_PATH) -> bool:
    result = load_result(path)
    if result is None or result.status not in {"booked", "booked_dry_run"}:
        return False
    pause_monitor(
        reason=result.status,
        specialty=result.specialty,
        slot=result.booked_slot,
    )
    return True


def should_alert_slots(slots: list[dict[str, Any]], path: Path = ALERTED_SLOTS_PATH) -> bool:
    if not slots:
        return False
    fingerprint = _slots_fingerprint(slots)
    if path.is_file() and path.read_text(encoding="utf-8").strip() == fingerprint:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fingerprint, encoding="utf-8")
    return True


def format_off_hours_heartbeat(specialty: str) -> str:
    return "\n".join(
        [
            "EDUS - monitor activo",
            f"Especialidad: {specialty}",
            "Sin cupos en esta revision.",
            "Sigo revisando cada ~20 min (fuera de 5-8am CR).",
        ]
    )
