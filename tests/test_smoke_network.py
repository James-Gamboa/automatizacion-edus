"""Smoke test: public EDUS page reachable (no credentials)."""

from __future__ import annotations

import pytest

from edus.constants import EDUS_BASE_URL


@pytest.mark.asyncio
async def test_edus_home_reachable() -> None:
    pytest.importorskip("playwright")
    from playwright.async_api import async_playwright

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
        response = await page.goto(EDUS_BASE_URL, wait_until="commit", timeout=120000)
        assert response is not None
        assert response.status < 500
        await page.wait_for_function(
            "() => !!document.getElementById('formInicioSesion')",
            timeout=120000,
        )
        html = await page.content()
        assert "formInicioSesion" in html
        await browser.close()
