"""Diagnose EDUS login page CAPTCHA URLs and response bodies."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from edus.constants import EDUS_BASE_URL


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-CR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(EDUS_BASE_URL, wait_until="commit")
        await page.wait_for_function(
            "() => !!document.getElementById('formInicioSesion')",
            timeout=120000,
        )
        info = await page.evaluate(
            """() => {
                const imgs = Array.from(document.querySelectorAll('img'))
                    .map((img) => ({src: img.src, id: img.id, w: img.naturalWidth, h: img.naturalHeight, alt: img.alt}));
                const captchaInput = document.getElementById('formInicioSesion:captchaDigitado');
                const links = Array.from(document.querySelectorAll('a, img, button'))
                    .filter((el) => /captcha|refresh|actualizar|codigo/i.test((el.outerHTML || '') + (el.title || '')))
                    .map((el) => ({tag: el.tagName, id: el.id, href: el.href || null, src: el.src || null, title: el.title || '', onclick: el.getAttribute('onclick')}));
                return {
                    url: location.href,
                    origin: location.origin,
                    hasCaptchaInput: !!captchaInput,
                    imgs,
                    links,
                    htmlHasCaptchaPath: document.documentElement.innerHTML.includes('/captcha'),
                };
            }"""
        )
        print("PAGE", info)

        # Probe candidate URLs
        candidates = []
        for img in info.get("imgs") or []:
            if img.get("src"):
                candidates.append(img["src"])
        candidates.extend(
            [
                f"{info['origin']}/CitasWebPF/captcha",
                "https://edus.ccss.sa.cr/CitasWebPF/captcha",
                f"{info['origin']}/eduscitasweb/captcha",
            ]
        )
        seen = set()
        for url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            resp = await page.request.get(url)
            body = await resp.body()
            ctype = resp.headers.get("content-type", "")
            print(
                f"GET {url} status={resp.status} ctype={ctype!r} "
                f"len={len(body)} magic={body[:16]!r}"
            )
            out = ROOT / "logs" / f"diag_{len(seen)}.bin"
            out.write_bytes(body)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
