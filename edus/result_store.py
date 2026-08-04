"""Persist and read last execution results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from edus.config import LAST_RESULT_PATH


@dataclass
class RunResult:
    status: str
    message: str
    specialty: str = ""
    booked: bool = False
    dry_run: bool = False
    slots_found: list[dict[str, Any]] = field(default_factory=list)
    slots_out_of_window: list[dict[str, Any]] = field(default_factory=list)
    booked_slot: Optional[dict[str, Any]] = None
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    exit_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save_result(result: RunResult, path: Path = LAST_RESULT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not result.finished_at:
        result.finished_at = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_result(path: Path = LAST_RESULT_PATH) -> Optional[RunResult]:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return RunResult(**data)


def format_result_summary(result: RunResult) -> str:
    lines = [
        f"Status: {result.status}",
        f"Message: {result.message}",
    ]
    if result.specialty:
        lines.append(f"Specialty: {result.specialty}")
    if result.booked_slot:
        lines.append(f"Booked: {result.booked_slot}")
    if result.slots_found:
        lines.append(f"In-window slots: {len(result.slots_found)}")
    if result.slots_out_of_window:
        lines.append(f"Out-of-window slots (not booked): {len(result.slots_out_of_window)}")
        for slot in result.slots_out_of_window[:5]:
            lines.append(f"  - {slot.get('fecha')} {slot.get('hora')}")
    if result.error:
        lines.append(f"Error: {result.error}")
    if result.finished_at:
        lines.append(f"Finished: {result.finished_at}")
    return "\n".join(lines)
