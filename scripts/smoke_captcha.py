"""Live CAPTCHA download smoke check (no credentials)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from edus.captcha import download_captcha, preprocess_captcha
from edus.constants import EDUS_BASE_URL


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CR",
        )
        page = await context.new_page()
        await page.goto(EDUS_BASE_URL, wait_until="commit")
        await page.wait_for_function(
            "() => !!document.getElementById('formInicioSesion')",
            timeout=120000,
        )
        dest = Path("logs/captcha_live.png")
        await download_captcha(page, dest)
        preprocess_captcha(dest, Path("logs/captcha_live_processed.png"))
        print(f"captcha_download_ok bytes={dest.stat().st_size}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
