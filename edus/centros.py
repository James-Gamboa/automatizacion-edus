"""Phase 1 — public health-center listing via JSF AJAX (no credentials)."""

from __future__ import annotations

import logging
import re
from typing import Any

from playwright.async_api import async_playwright

from edus.constants import EDUS_BASE_URL

logger = logging.getLogger("edus.centros")

CENTRO_URL = "https://edus.ccss.sa.cr/CitasWebPF/faces/xhtml/centroSalud/centroSalud.xhtml"


def _extract_viewstate(html: str) -> str:
    match = re.search(
        r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"',
        html,
    )
    if not match:
        match = re.search(
            r'id="j_id1:javax\.faces\.ViewState:0"[^>]*value="([^"]+)"',
            html,
        )
    if not match:
        raise RuntimeError("Could not extract javax.faces.ViewState from centroSalud page")
    return match.group(1)


def _parse_table_rows(html_fragment: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_fragment, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.I | re.S)
        if len(cells) < 2:
            continue
        clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if not any(clean):
            continue
        rows.append(
            {
                "col0": clean[0] if len(clean) > 0 else "",
                "col1": clean[1] if len(clean) > 1 else "",
                "col2": clean[2] if len(clean) > 2 else "",
                "raw": " | ".join(clean),
            }
        )
    return rows


async def list_centros(filter_area: str = "", rows: int = 20) -> list[dict[str, Any]]:
    """
    Fetch public centroSalud table: open page for ViewState/cookies, then
    POST partial/ajax pagination/filter as documented in the guide.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(CENTRO_URL, wait_until="commit", timeout=120000)
        try:
            await page.wait_for_function(
                "() => document.body && document.body.innerHTML.length > 5000 && !window.bobcmn",
                timeout=120000,
            )
        except Exception:
            await page.wait_for_timeout(5000)
        html = await page.content()
        viewstate = _extract_viewstate(html)

        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.ViewState": viewstate,
            "formSIAC:tablaCentroSalud_pagination": "true",
            "formSIAC:tablaCentroSalud_first": "0",
            "formSIAC:tablaCentroSalud_rows": str(rows),
        }
        if filter_area:
            data["formSIAC:tablaCentroSalud:globalFilter"] = filter_area

        response = await page.request.post(
            CENTRO_URL,
            form=data,
            headers={
                "Faces-Request": "partial/ajax",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if not response.ok:
            body_preview = (await response.text())[:300]
            await browser.close()
            raise RuntimeError(
                f"centroSalud AJAX failed: HTTP {response.status} {body_preview}"
            )
        raw = await response.body()
        text = raw.decode("iso-8859-1", errors="replace")
        await browser.close()

    chunks = re.findall(r"<!\[CDATA\[(.*?)\]\]>", text, flags=re.S)
    fragment = "\n".join(chunks) if chunks else text
    parsed = _parse_table_rows(fragment)
    logger.info("Listed %s centro rows (filter=%r)", len(parsed), filter_area)
    return parsed


async def probe_login_page() -> dict[str, Any]:
    """Lightweight connectivity check against the login URL."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CR",
        )
        page = await context.new_page()
        try:
            response = await page.goto(
                EDUS_BASE_URL,
                wait_until="commit",
                timeout=120000,
            )
            status = response.status if response else None
            await page.wait_for_function(
                "() => !!document.getElementById('formInicioSesion')",
                timeout=120000,
            )
            html = await page.content()
        except Exception as exc:
            await browser.close()
            return {
                "url": EDUS_BASE_URL,
                "status": None,
                "error": str(exc),
                "has_login_form": False,
                "has_captcha_hint": False,
            }
        await browser.close()
    return {
        "url": EDUS_BASE_URL,
        "status": status,
        "has_login_form": "formInicioSesion" in html,
        "has_captcha_hint": "captcha" in html.lower(),
    }
