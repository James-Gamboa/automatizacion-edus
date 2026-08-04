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
