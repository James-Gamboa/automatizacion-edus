#!/usr/bin/env python3
"""Book an EDUS slot immediately from a Telegram button text. No LLM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edus.fast_book import (  # noqa: E402
    acquire_lock,
    format_book_reply,
    last_result,
    parse_reserve_intent,
    release_lock,
    run_book_cli,
)
from edus.telegram_buttons import send_telegram_message  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast EDUS reserve from Telegram text")
    parser.add_argument("--message", required=True, help="Telegram message / button text")
    parser.add_argument("--no-ack", action="store_true", help="Do not send the starting Telegram ping")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    intent = parse_reserve_intent(args.message, last_result())
    if intent is None:
        send_telegram_message("No entendi que cita reservar.")
        return 1
    if not acquire_lock():
        send_telegram_message("Ya hay una reserva en curso. Espera a que termine.")
        return 0

    fecha = intent.get("fecha") or ""
    hora = intent.get("hora") or ""
    specialty = intent.get("specialty") or "medicina_general"
    target = " ".join(part for part in (fecha, hora) if part).strip() or "primer cupo"
    try:
        if not args.no_ack:
            send_telegram_message(f"Reservando {target} ({specialty}). Voy directo a EDUS.")
        run_book_cli(specialty=specialty, fecha=fecha or None, hora=hora or None)
        send_telegram_message(format_book_reply(last_result()))
        return 0
    except Exception as exc:
        send_telegram_message(f"EDUS: fallo al reservar. {exc}")
        return 1
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
