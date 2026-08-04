"""Playwright browser lifecycle helpers."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from edus.config import Settings

logger = logging.getLogger("edus.browser")

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-default-browser-check",
    "--no-first-run",
]


@asynccontextmanager
async def open_browser(settings: Settings) -> AsyncIterator[tuple[Browser, BrowserContext, Page]]:
    playwright = await async_playwright().start()
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    try:
        launch_kwargs: dict = {
            "headless": settings.headless,
            "slow_mo": settings.slow_mo_ms,
            "args": list(STEALTH_ARGS),
        }
        channel = settings.browser_channel or ""
        browser = None

        if channel:
            try:
                browser = await playwright.chromium.launch(
                    **{**launch_kwargs, "channel": channel}
                )
                logger.info("Using browser channel=%s", channel)
            except Exception as exc:
                logger.warning("Channel %s failed (%s); falling back", channel, exc)
                channel = ""

        if browser is None:
            for candidate in ("chrome", "msedge"):
                try:
                    browser = await playwright.chromium.launch(
                        **{**launch_kwargs, "channel": candidate}
                    )
                    channel = candidate
                    logger.info("Using browser channel=%s", candidate)
                    break
                except Exception:
                    browser = None

        if browser is None:
            try:
                browser = await playwright.chromium.launch(**launch_kwargs)
                channel = "chromium"
                logger.info("Using bundled Chromium")
            except Exception as exc:
                raise RuntimeError(
                    "Playwright Chromium is not installed. Run: python -m playwright install chromium"
                ) from exc

        context = await browser.new_context(
            locale="es-CR",
            timezone_id="America/Costa_Rica",
            ignore_https_errors=True,
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        context.set_default_timeout(settings.action_timeout_ms)
        context.set_default_navigation_timeout(settings.navigation_timeout_ms)
        page = await context.new_page()
        logger.info("Browser started (headless=%s channel=%s)", settings.headless, channel or "chromium")
        yield browser, context, page
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
        logger.info("Browser closed")


async def wait_ajax(page: Page, seconds: float) -> None:
    await page.wait_for_timeout(int(seconds * 1000))
