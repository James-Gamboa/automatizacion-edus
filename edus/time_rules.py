"""Time-window rules for monitoring and slot booking (Costa Rica)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from edus.constants import TZ_COSTA_RICA


def _costa_rica_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo(TZ_COSTA_RICA)
        except Exception:
            pass
    # Fallback: Costa Rica is UTC-6 year-round (no DST)
    return timezone(timedelta(hours=-6), name="UTC-6")


def parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid time '{value}', expected HH:MM")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def now_costa_rica(now: Optional[datetime] = None) -> datetime:
    tz = _costa_rica_tz()
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def is_within_monitor_window(
    *,
    start_hour: int = 5,
    end_hour: int = 8,
    now: Optional[datetime] = None,
) -> bool:
    """True when current Costa Rica hour is in [start_hour, end_hour)."""
    current = now_costa_rica(now)
    return start_hour <= current.hour < end_hour


def normalize_slot_time(raw: str) -> Optional[time]:
    """Parse slot times like '07:30', '7:30 a.m.', '07:30:00'."""
    text = (raw or "").strip().lower()
    if not text:
        return None
    text = (
        text.replace("a.m.", "")
        .replace("p.m.", "")
        .replace("am", "")
        .replace("pm", "")
        .replace(" ", "")
    )
    # Keep only first HH:MM[:SS]
    digits = []
    colons = 0
    for ch in text:
        if ch.isdigit():
            digits.append(ch)
        elif ch == ":" and colons < 2:
            digits.append(ch)
            colons += 1
        elif digits:
            break
    candidate = "".join(digits)
    if not candidate:
        return None
    parts = candidate.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if "p.m" in (raw or "").lower() or "pm" in (raw or "").lower().replace(".", ""):
            if hour < 12:
                hour += 12
        if "a.m" in (raw or "").lower() or (
            "am" in (raw or "").lower().replace(".", "") and "p" not in (raw or "").lower()
        ):
            if hour == 12:
                hour = 0
        return time(hour=hour, minute=minute)
    except (ValueError, IndexError):
        return None


def is_slot_within_booking_window(
    slot_time_raw: str,
    *,
    start: str = "05:00",
    end: str = "08:00",
) -> bool:
    """Inclusive start, exclusive end on the clock (05:00 <= t < 08:00 by default)."""
    slot = normalize_slot_time(slot_time_raw)
    if slot is None:
        return False
    start_t = parse_hhmm(start)
    end_t = parse_hhmm(end)
    return start_t <= slot < end_t


def slot_matches_prefer(
    fecha: str,
    hora: str,
    prefer_fecha: Optional[str] = None,
    prefer_hora: Optional[str] = None,
) -> bool:
    """True when a cupo matches the Telegram button the user tapped."""
    want_fecha = (prefer_fecha or "").strip()
    want_hora = (prefer_hora or "").strip()
    if want_fecha and want_fecha not in (fecha or ""):
        return False
    if want_hora:
        got = normalize_slot_time(hora or "")
        want = normalize_slot_time(want_hora)
        if got is None or want is None or got != want:
            return False
    return bool(want_fecha or want_hora)
