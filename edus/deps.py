"""Dependency validation and optional auto-install helpers."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


@dataclass
class CheckItem:
    name: str
    ok: bool
    detail: str


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_dependencies() -> list[CheckItem]:
    items: list[CheckItem] = []

    items.append(
        CheckItem(
            "python",
            sys.version_info >= (3, 10),
            f"{sys.version.split()[0]} (requires >= 3.10)",
        )
    )
    items.append(
        CheckItem("playwright", _has_module("playwright"), "pip package playwright")
    )
    items.append(CheckItem("PIL", _has_module("PIL"), "pip package pillow"))
    items.append(
        CheckItem(
            "dotenv",
            _has_module("dotenv"),
            "pip package python-dotenv (optional but recommended)",
        )
    )

    tess = shutil.which("tesseract")
    if not tess:
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if shutil.which(candidate) or __import__("pathlib").Path(candidate).exists():
                tess = candidate
                break
    items.append(
        CheckItem(
            "tesseract",
            bool(tess),
            tess or "Install Tesseract OCR and/or set TESSERACT_CMD",
        )
    )

    # Chromium presence is best-effort
    chromium_ok = False
    chromium_detail = "unknown"
    if _has_module("playwright"):
        try:
            from playwright.__main__ import main as _  # noqa: F401

            chromium_ok = True
            chromium_detail = "playwright installed (run: python -m playwright install chromium)"
        except Exception as exc:
            chromium_detail = str(exc)
    items.append(CheckItem("playwright_runtime", chromium_ok, chromium_detail))
    return items


def ensure_playwright_browsers(log: Callable[[str], None] = print) -> None:
    log("Installing Playwright Chromium…")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )


def print_report(items: list[CheckItem]) -> int:
    exit_code = 0
    for item in items:
        mark = "OK" if item.ok else "FAIL"
        if not item.ok and item.name in {"python", "playwright", "PIL", "tesseract"}:
            exit_code = 1
        print(f"[{mark}] {item.name}: {item.detail}")
    return exit_code
