"""Unit tests for EDUS time rules, filters, and config (no live portal)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from edus.booking import Slot, filter_slots
from edus.config import Settings
from edus.constants import ALIAS_TO_PRESET, SPECIALTY_PRESETS
from edus.result_store import RunResult, format_result_summary, load_result, save_result
from edus.time_rules import (
    is_slot_within_booking_window,
    is_within_monitor_window,
    normalize_slot_time,
    slot_matches_prefer,
)


def test_aliases_resolve() -> None:
    assert ALIAS_TO_PRESET["medicina"] == "medicina_general"
    assert ALIAS_TO_PRESET["odontología"] == "odontologia"
    assert "medicina_general" in SPECIALTY_PRESETS
    assert "odontologia" in SPECIALTY_PRESETS


def test_monitor_window_costa_rica() -> None:
    tz = timezone(timedelta(hours=-6))
    assert is_within_monitor_window(now=datetime(2026, 7, 30, 5, 0, tzinfo=tz))
    assert is_within_monitor_window(now=datetime(2026, 7, 30, 7, 59, tzinfo=tz))
    assert not is_within_monitor_window(now=datetime(2026, 7, 30, 8, 0, tzinfo=tz))
    assert not is_within_monitor_window(now=datetime(2026, 7, 30, 4, 59, tzinfo=tz))


def test_image_and_waf_detection() -> None:
    from edus.captcha import is_image_bytes, looks_like_waf_rejection

    assert is_image_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 200)
    assert not is_image_bytes(b"<html>Request Rejected</html>")
    assert looks_like_waf_rejection("<html><title>Request Rejected</title></html>")
    assert looks_like_waf_rejection(b"The requested URL was rejected. Support ID is: 123")


def test_filter_slots_excludes_out_of_window_and_dates() -> None:
    settings = Settings(
        cedula="000",
        clave="x",
        excluir_fechas=["15/08/2026"],
        enforce_slot_window=True,
        slot_start="05:00",
        slot_end="08:00",
    )
    slots = [
        Slot("14/08/2026", "07:00", "1", "A", "Dr", 0),
        Slot("14/08/2026", "09:00", "2", "A", "Dr", 1),
        Slot("15/08/2026", "07:00", "3", "A", "Dr", 2),
    ]
    inn, out = filter_slots(slots, settings)
    assert len(inn) == 1
    assert inn[0].hora == "07:00"
    assert len(out) == 2


def test_telegram_alert_lists_out_of_window_and_booked() -> None:
    from edus.watchdog import format_telegram_result

    listed = format_telegram_result(
        RunResult(
            status="slots_out_of_window",
            message="Found 1 slot(s) outside booking window (05:00-08:00)",
            specialty="Medicina General",
            slots_out_of_window=[{"fecha": "14/08/2026", "hora": "09:00"}],
        )
    )
    assert listed.startswith("VIBRI\n")
    assert "14/08/2026 09:00" in listed
    assert "Toca el boton" in listed
    assert "NO reservadas" in listed
    assert "Responde" not in listed

    reserved = format_telegram_result(
        RunResult(
            status="booked",
            message="Booked",
            specialty="Medicina General",
            booked=True,
            booked_slot={"fecha": "14/08/2026", "hora": "07:00"},
        )
    )
    assert "CITA RESERVADA" in reserved
    assert "07:00" in reserved


def test_telegram_reserve_buttons_and_preferred_slot() -> None:
    from edus.telegram_buttons import reply_keyboard, reservation_command

    assert reservation_command("14/08/2026", "07:00") == "reserva esta 14/08/2026 07:00"
    assert reservation_command("Fecha20/08/2026", "Hora de Cita11:00 A.M.") == (
        "reserva esta 20/08/2026 11:00"
    )
    keyboard = reply_keyboard(
        [
            {"fecha": "14/08/2026", "hora": "07:00"},
            {"fecha": "14/08/2026", "hora": "09:00"},
        ]
    )
    labels = [row[0]["text"] for row in keyboard["keyboard"]]
    assert labels == [
        "reserva esta 14/08/2026 07:00",
        "reserva esta 14/08/2026 09:00",
    ]
    assert keyboard["one_time_keyboard"] is True
    assert slot_matches_prefer("14/08/2026", "07:00", "14/08/2026", "07:00")
    assert not slot_matches_prefer("14/08/2026", "09:00", "14/08/2026", "07:00")


def test_parse_fast_reserve_button_and_primero() -> None:
    from edus.fast_book import is_fast_reserve_message, parse_reserve_intent

    assert is_fast_reserve_message("reserva esta 14/08/2026 07:00")
    parsed = parse_reserve_intent("reserva esta 14/08/2026 07:00")
    assert parsed == {
        "fecha": "14/08/2026",
        "hora": "07:00",
        "specialty": "medicina_general",
    }
    last = RunResult(
        status="slots_available",
        message="ok",
        specialty="Odontología",
        slots_found=[{"fecha": "15/08/2026", "hora": "06:30"}],
        slots_out_of_window=[{"fecha": "15/08/2026", "hora": "09:00"}],
    )
    primero = parse_reserve_intent("ok, reservame el primero", last)
    assert primero is not None
    assert primero["fecha"] == "15/08/2026"
    assert primero["hora"] == "06:30"
    assert primero["specialty"] == "odontologia"
    picked = parse_reserve_intent("ok, escogeme el de las 09:00", last)
    assert picked is not None
    assert picked["hora"] == "09:00"
    assert not is_fast_reserve_message("hay cupos?")


def test_monitor_pause_and_alert_dedupe(tmp_path: Path) -> None:
    from edus.monitor_state import (
        format_off_hours_heartbeat,
        is_monitor_paused,
        pause_monitor,
        resume_monitor,
        should_alert_slots,
    )

    pause_path = tmp_path / "paused.json"
    alert_path = tmp_path / "alerted.txt"
    slots = [{"fecha": "14/08/2026", "hora": "07:00"}]

    assert not is_monitor_paused(pause_path)
    assert should_alert_slots(slots, alert_path)
    assert not should_alert_slots(slots, alert_path)

    pause_monitor(specialty="Medicina General", slot=slots[0], path=pause_path)
    assert is_monitor_paused(pause_path)
    resume_monitor(pause_path)
    assert not is_monitor_paused(pause_path)

    heartbeat = format_off_hours_heartbeat("Medicina General")
    assert "monitor activo" in heartbeat
    assert "Sin cupos" in heartbeat


def test_result_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "last_result.json"
    result = RunResult(status="booked", message="ok", specialty="Medicina General", booked=True)
    save_result(result, path)
    loaded = load_result(path)
    assert loaded is not None
    assert loaded.status == "booked"
    summary = format_result_summary(loaded)
    assert "booked" in summary.lower() or "Status" in summary


def test_settings_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EDUS_CEDULA", raising=False)
    monkeypatch.delenv("EDUS_CLAVE", raising=False)
    # Prevent .env from loading real secrets during test: point ROOT away? 
    # load_settings reads process env after dotenv — clear and use empty fake env file.
    from edus import config as cfg

    monkeypatch.setattr(cfg, "_load_dotenv", lambda: None)
    with pytest.raises(RuntimeError, match="EDUS_CEDULA"):
        cfg.load_settings(require_credentials=True)


def test_resolve_preset_medicina(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDUS_CEDULA", "123")
    monkeypatch.setenv("EDUS_CLAVE", "secret")
    from edus import config as cfg

    monkeypatch.setattr(cfg, "_load_dotenv", lambda: None)
    settings = cfg.load_settings()
    preset = settings.resolve_preset("medicina general")
    assert preset["especialidad_code"] == "1033"
    assert preset["servicio_code"] == "1"
