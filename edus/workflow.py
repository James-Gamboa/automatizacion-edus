"""End-to-end EDUS check-and-book workflow."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from edus.booking import (
    book_slot,
    click_agregar_cita_titular,
    ensure_centro_salud_note,
    filter_slots,
    has_existing_appointment_same_day,
    parse_cupos,
    read_page_errors,
    select_especialidad,
    select_servicio,
)
from edus.browser import open_browser
from edus.config import Settings, load_settings
from edus.familiar import switch_to_familiar
from edus.login import login
from edus.result_store import RunResult, save_result
from edus.time_rules import is_within_monitor_window, slot_matches_prefer

logger = logging.getLogger("edus.workflow")


async def check_and_book(
    specialty: str = "medicina_general",
    *,
    settings: Optional[Settings] = None,
    force: bool = False,
    book: bool = True,
    any_time: bool = False,
    prefer_fecha: Optional[str] = None,
    prefer_hora: Optional[str] = None,
) -> RunResult:
    """
    Full flow:
      1) Login + CAPTCHA retries
      2) Optional family switch
      3) Select service + specialty
      4) Parse cupos, filter EXCLUIR_FECHAS + slot window
      5) Book first valid slot (unless check-only / dry-run)
    """
    started = datetime.now(timezone.utc).isoformat()
    settings = settings or load_settings()
    preset = settings.resolve_preset(specialty)

    result = RunResult(
        status="started",
        message="Workflow started",
        specialty=preset["label"],
        dry_run=settings.dry_run,
        started_at=started,
    )

    if settings.enforce_monitor_window and not force:
        if not is_within_monitor_window(
            start_hour=settings.monitor_start_hour,
            end_hour=settings.monitor_end_hour,
        ):
            result.status = "outside_monitor_window"
            result.message = (
                f"Outside monitor window "
                f"({settings.monitor_start_hour}:00–{settings.monitor_end_hour}:00 America/Costa_Rica). "
                "Use --force to run anyway."
            )
            result.exit_code = 0
            save_result(result)
            return result

    try:
        async with open_browser(settings) as (_browser, _context, page):
            await login(page, settings)
            await ensure_centro_salud_note(page, settings)

            if settings.familiar_cedula or settings.familiar_nombre:
                await switch_to_familiar(page, settings)
            else:
                await click_agregar_cita_titular(page, settings)

            await select_servicio(page, preset, settings)
            await select_especialidad(page, preset, settings)

            errors = await read_page_errors(page)
            if any("no_slots" in e for e in errors):
                result.status = "no_slots"
                result.message = "No se encontraron cupos disponibles"
                result.exit_code = 0
                save_result(result)
                return result

            slots = await parse_cupos(page)
            wants_specific = bool((prefer_fecha or "").strip() or (prefer_hora or "").strip())
            filter_settings = (
                replace(settings, enforce_slot_window=False)
                if any_time or wants_specific
                else settings
            )
            in_window, out_window = filter_slots(slots, filter_settings)
            result.slots_found = [s.as_dict() for s in in_window]
            result.slots_out_of_window = [s.as_dict() for s in out_window]

            if wants_specific:
                matched = [
                    slot
                    for slot in [*in_window, *out_window]
                    if slot_matches_prefer(
                        slot.fecha,
                        slot.hora,
                        prefer_fecha=prefer_fecha,
                        prefer_hora=prefer_hora,
                    )
                ]
                if not matched:
                    result.status = "no_slots"
                    result.message = (
                        f"No hay cupo {prefer_fecha or ''} {prefer_hora or ''}".strip()
                    )
                    result.exit_code = 0
                    save_result(result)
                    return result
                in_window = matched
                out_window = []
                result.slots_found = [s.as_dict() for s in in_window]
                result.slots_out_of_window = []

            if out_window and not in_window:
                result.status = "slots_out_of_window"
                listed = ", ".join(
                    f"{s.fecha} {s.hora}" for s in out_window[:5]
                )
                result.message = (
                    f"Found {len(out_window)} slot(s) outside booking window "
                    f"({settings.slot_start}-{settings.slot_end}): {listed}; none reserved."
                )
                result.exit_code = 0
                save_result(result)
                return result

            if not in_window:
                result.status = "no_slots"
                result.message = "No bookable slots after filters"
                result.exit_code = 0
                save_result(result)
                return result

            if not book:
                result.status = "slots_available"
                result.message = f"Found {len(in_window)} in-window slot(s); check-only mode"
                result.exit_code = 0
                save_result(result)
                return result

            for slot in in_window:
                if await has_existing_appointment_same_day(page, slot.fecha):
                    logger.info("Skipping %s — existing appointment same day", slot.fecha)
                    continue
                ok = await book_slot(page, slot, settings)
                if ok:
                    result.booked = True
                    result.booked_slot = slot.as_dict()
                    result.status = "booked_dry_run" if settings.dry_run else "booked"
                    result.message = (
                        f"{'DRY RUN: would book' if settings.dry_run else 'Booked'} "
                        f"{preset['label']} on {slot.fecha} at {slot.hora}"
                    )
                    result.exit_code = 0
                    save_result(result)
                    return result

            result.status = "booking_failed"
            result.message = "Slots found but booking failed or duplicates blocked all"
            result.exit_code = 1
            save_result(result)
            return result

    except Exception as exc:
        from edus.login import WafRejectedError

        logger.exception("Workflow error")
        result.status = "waf_rejected" if isinstance(exc, WafRejectedError) else "error"
        result.message = (
            "Blocked by EDUS WAF — wait 15–30 minutes, then retry with --headed"
            if isinstance(exc, WafRejectedError)
            else "Workflow failed"
        )
        result.error = str(exc)
        result.exit_code = 1
        save_result(result)
        return result
