#!/usr/bin/env python3
"""EDUS Citas CLI — entrypoint used by the agent skill and Task Scheduler."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edus.config import load_settings  # noqa: E402
from edus.deps import check_dependencies, ensure_playwright_browsers, print_report  # noqa: E402
from edus.logging_setup import setup_logging  # noqa: E402
from edus.result_store import format_result_summary, load_result  # noqa: E402
from edus.watchdog import run_watchdog  # noqa: E402
from edus.workflow import check_and_book  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edus",
        description="EDUS Citas CCSS automation (Playwright + CAPTCHA OCR)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    book = sub.add_parser("book", help="Login, search, and reserve a slot")
    book.add_argument(
        "--specialty",
        "-s",
        default="medicina_general",
        help="medicina_general | odontologia (aliases: medicina, odonto)",
    )
    book.add_argument(
        "--force",
        action="store_true",
        help="Ignore monitor window (5am–8am CR)",
    )
    book.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not confirm reservation",
    )
    book.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window",
    )

    check = sub.add_parser("check", help="Check availability without booking")
    check.add_argument("--specialty", "-s", default="medicina_general")
    check.add_argument("--force", action="store_true")
    check.add_argument("--headed", action="store_true")

    monitor = sub.add_parser("monitor", help="Watchdog mode (silent when no slots)")
    monitor.add_argument("--specialty", "-s", default="medicina_general")
    monitor.add_argument("--force", action="store_true")
    monitor.add_argument(
        "--check-only",
        action="store_true",
        help="Alert when slots exist; do NOT auto-book (you confirm later)",
    )

    sub.add_parser("last", help="Show last execution result")
    sub.add_parser("validate", help="Validate dependencies")
    sub.add_parser("probe", help="Probe EDUS login page connectivity")

    centros = sub.add_parser("centros", help="List public health centers (Phase 1)")
    centros.add_argument("--filter", "-f", default="", help="globalFilter area name")
    centros.add_argument("--rows", type=int, default=20)

    install = sub.add_parser("install-browsers", help="Install Playwright Chromium")
    install.add_argument("--yes", action="store_true")

    return parser


def _apply_runtime_flags(args: argparse.Namespace) -> None:
    import os

    if getattr(args, "dry_run", False):
        os.environ["EDUS_DRY_RUN"] = "1"
    if getattr(args, "headed", False):
        os.environ["EDUS_HEADLESS"] = "0"


async def _cmd_book(args: argparse.Namespace) -> int:
    _apply_runtime_flags(args)
    settings = load_settings()
    logger = setup_logging(settings.log_level)
    logger.info("Starting book specialty=%s force=%s", args.specialty, args.force)
    result = await check_and_book(
        args.specialty, settings=settings, force=args.force, book=True
    )
    print(format_result_summary(result))
    return result.exit_code


async def _cmd_check(args: argparse.Namespace) -> int:
    _apply_runtime_flags(args)
    settings = load_settings()
    setup_logging(settings.log_level)
    result = await check_and_book(
        args.specialty, settings=settings, force=args.force, book=False
    )
    print(format_result_summary(result))
    return result.exit_code


async def _cmd_monitor(args: argparse.Namespace) -> int:
    settings = load_settings()
    setup_logging(settings.log_level)
    return await run_watchdog(
        args.specialty,
        settings=settings,
        force=args.force,
        check_only=bool(getattr(args, "check_only", False)),
    )


def _cmd_last() -> int:
    result = load_result()
    if result is None:
        print("No previous result found (data/last_result.json).")
        return 0
    print(format_result_summary(result))
    print("\n--- JSON ---")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


async def _cmd_centros(args: argparse.Namespace) -> int:
    from edus.centros import list_centros

    setup_logging("INFO")
    rows = await list_centros(filter_area=args.filter, rows=args.rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


async def _cmd_probe() -> int:
    from edus.centros import probe_login_page

    info = await probe_login_page()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info.get("status") and info["status"] < 500 else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return print_report(check_dependencies())
    if args.command == "install-browsers":
        ensure_playwright_browsers()
        return 0
    if args.command == "last":
        return _cmd_last()
    if args.command == "probe":
        return asyncio.run(_cmd_probe())
    if args.command == "centros":
        return asyncio.run(_cmd_centros(args))
    if args.command == "book":
        return asyncio.run(_cmd_book(args))
    if args.command == "check":
        return asyncio.run(_cmd_check(args))
    if args.command == "monitor":
        return asyncio.run(_cmd_monitor(args))
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
