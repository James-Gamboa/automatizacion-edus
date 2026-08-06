"""Watchdog behavior for cron / Task Scheduler (guide Phase 5)."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from edus.config import Settings, load_settings
from edus.result_store import RunResult, format_result_summary
from edus.time_rules import is_within_monitor_window
from edus.workflow import check_and_book

logger = logging.getLogger("edus.watchdog")


def _format_slots_alert(result: RunResult) -> str:
    lines = [
        "EDUS: hay cupos disponibles",
        f"Especialidad: {result.specialty}",
        f"Estado: {result.status}",
        result.message,
        "",
        "Cupos (responde OK + fecha/hora para reservar, o 'reserva el primero'):",
    ]
    for i, slot in enumerate(result.slots_found or [], start=1):
        fecha = slot.get("fecha", "?")
        hora = slot.get("hora", "?")
        consultorio = slot.get("consultorio", "")
        lines.append(f"  {i}. {fecha} {hora}" + (f" — {consultorio}" if consultorio else ""))
    if result.slots_out_of_window:
        lines.append("")
        lines.append(f"(También {len(result.slots_out_of_window)} fuera de ventana de horario)")
    return "\n".join(lines)


async def run_watchdog(
    specialty: str = "medicina_general",
    *,
    settings: Optional[Settings] = None,
    force: bool = False,
    check_only: bool = False,
) -> int:
    """
    Exit semantics (official guide):
      - No cupos → silent exit 0 (no stdout)
      - With cupos / booking action → print result, exit 0
      - Error → print error, exit 1

    check_only=True: never auto-book; only alert when slots exist
    (you confirm later with `book` or reply OK to the agent).
    """
    settings = settings or load_settings()

    if settings.enforce_monitor_window and not force:
        if not is_within_monitor_window(
            start_hour=settings.monitor_start_hour,
            end_hour=settings.monitor_end_hour,
        ):
            return 0

    result: RunResult = await check_and_book(
        specialty,
        settings=settings,
        force=True,
        book=not check_only,
    )

    if result.status in {"no_slots", "outside_monitor_window"}:
        return 0

    if result.status == "error" or result.exit_code != 0:
        print(format_result_summary(result), file=sys.stderr)
        return 1

    if check_only and result.status in {
        "slots_available",
        "slots_out_of_window",
    }:
        print(_format_slots_alert(result))
        return 0

    print(format_result_summary(result))
    return 0
