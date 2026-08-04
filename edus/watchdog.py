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


async def run_watchdog(
    specialty: str = "medicina_general",
    *,
    settings: Optional[Settings] = None,
    force: bool = False,
) -> int:
    """
    Exit semantics (official guide):
      - No cupos → silent exit 0 (no stdout)
      - With cupos / booking action → print result, exit 0
      - Error → print error, exit 1
    """
    settings = settings or load_settings()

    if settings.enforce_monitor_window and not force:
        if not is_within_monitor_window(
            start_hour=settings.monitor_start_hour,
            end_hour=settings.monitor_end_hour,
        ):
            return 0

    result: RunResult = await check_and_book(
        specialty, settings=settings, force=True, book=True
    )

    if result.status in {"no_slots", "outside_monitor_window"}:
        return 0

    if result.status == "error" or result.exit_code != 0:
        print(format_result_summary(result), file=sys.stderr)
        return 1

    print(format_result_summary(result))
    return 0
