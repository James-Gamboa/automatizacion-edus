"""Watchdog behavior for cron / Task Scheduler (guide Phase 5)."""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from edus.config import Settings, load_settings
from edus.result_store import RunResult
from edus.time_rules import is_within_monitor_window
from edus.workflow import check_and_book

logger = logging.getLogger("edus.watchdog")


def _slot_line(slot: dict[str, Any], index: int) -> str:
    fecha = slot.get("fecha", "?")
    hora = slot.get("hora", "?")
    extra = slot.get("consultorio") or slot.get("funcionario") or ""
    suffix = f" {extra}" if extra else ""
    return f"  {index}. {fecha} {hora}{suffix}"


def _slot_block(slot: dict[str, Any], index: int) -> list[str]:
    return [_slot_line(slot, index)]


def format_telegram_result(result: RunResult) -> str:
    """Plain UTF-8 text for Hermes --no-agent Telegram delivery (no LLM reply needed)."""
    if result.status in {"booked", "booked_dry_run"}:
        slot = result.booked_slot or {}
        title = (
            "EDUS - CITA RESERVADA (dry-run)"
            if result.status == "booked_dry_run"
            else "EDUS - CITA RESERVADA"
        )
        lines = [
            title,
            f"Especialidad: {result.specialty}",
            f"Fecha: {slot.get('fecha', '?')}",
            f"Hora: {slot.get('hora', '?')}",
        ]
        if slot.get("consultorio"):
            lines.append(f"Consultorio: {slot['consultorio']}")
        lines.append("")
        lines.append("No hace falta responder. El cron ya reservo.")
        return "\n".join(lines)

    if result.status in {"error", "waf_rejected", "booking_failed"}:
        return "\n".join(
            [
                "EDUS - no se pudo completar",
                f"Especialidad: {result.specialty}",
                f"Estado: {result.status}",
                result.message.replace("\u2013", "-").replace("\u2014", "-"),
                result.error or "",
            ]
        ).strip()

    all_slots = list(result.slots_found or []) + list(result.slots_out_of_window or [])
    lines = [
        "VIBRI",
        "EDUS - hay citas (NO reservadas)",
        f"Especialidad: {result.specialty}",
        "",
        "Lista:",
    ]
    if all_slots:
        for i, slot in enumerate(all_slots, start=1):
            lines.extend(_slot_block(slot, i))
        lines.append("")
        lines.append("Toca el boton de abajo para reservar esa cita.")
    else:
        lines.append("  (sin detalle de hora)")
    return "\n".join(lines)


async def run_watchdog(
    specialty: str = "medicina_general",
    *,
    settings: Optional[Settings] = None,
    force: bool = False,
    check_only: bool = False,
    any_time: bool = False,
) -> int:
    """
    Exit semantics (official guide):
      - No cupos -> silent exit 0 (no stdout)
      - With cupos / booking action -> print result, exit 0
      - Error -> print error, exit 1

    check_only=True: never auto-book; only Telegram a list when slots exist
    any_time=True: include slots whose hour is outside 05:00-08:00
    force=True: still search outside the 5-8am monitor window (silent if no cupos)
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
        any_time=any_time,
    )

    if result.status in {"no_slots", "outside_monitor_window"}:
        return 0

    text = format_telegram_result(result)
    if result.status == "error" or result.exit_code != 0:
        print(text, file=sys.stderr)
        return 1

    slots = list(result.slots_found or []) + list(result.slots_out_of_window or [])
    if slots:
        from edus.telegram_buttons import send_cupos_alert

        if send_cupos_alert(text, slots):
            return 0

    print(text)
    return 0
