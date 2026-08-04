"""Compare launch strategies against EDUS bot protection."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright


async def try_launch(label: str, launch_kwargs: dict) -> bool:
    print("TRY", label)
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(**launch_kwargs)
        except Exception as exc:
            print(" launch fail", exc)
            return False
        context = await browser.new_context(
            locale="es-CR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()
        try:
            await page.goto(
                "https://edus.ccss.sa.cr/eduscitasweb/",
                wait_until="commit",
                timeout=60000,
            )
            await page.wait_for_function(
                "() => !!document.getElementById('formInicioSesion')",
                timeout=45000,
            )
            html = await page.content()
            print(" OK", label, "len", len(html), "captcha", "captcha" in html.lower())
            imgs = await page.evaluate(
                "() => Array.from(document.images).map(i => "
                "({src:i.src,w:i.naturalWidth,h:i.naturalHeight,id:i.id}))"
            )
            print(" imgs", imgs)
            for img in imgs:
                src = img.get("src") or ""
                if "captcha" in src.lower() or (img.get("w") or 0) > 100:
                    resp = await page.request.get(src)
                    body = await resp.body()
                    print(" imgget", src, resp.status, len(body), body[:12])
                    (ROOT / "logs" / "diag_captcha.bin").write_bytes(body)
            # also probe endpoint
            origin = await page.evaluate("() => location.origin")
            for url in (
                f"{origin}/CitasWebPF/captcha",
                "https://edus.ccss.sa.cr/CitasWebPF/captcha",
            ):
                resp = await page.request.get(url)
                body = await resp.body()
                ctype = resp.headers.get("content-type", "")
                print(" endpoint", url, resp.status, ctype, len(body), body[:12])
            await browser.close()
            return True
        except Exception as exc:
            print(" FAIL", label, type(exc).__name__, str(exc)[:250])
            try:
                print(" html_len", len(await page.content()), "url", page.url)
                print((await page.content())[:500])
            except Exception:
                pass
            await browser.close()
            return False


async def main() -> None:
    strategies = [
        (
            "headless_stealth",
            {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            },
        ),
        (
            "chrome_headless",
            {
                "headless": True,
                "channel": "chrome",
                "args": ["--disable-blink-features=AutomationControlled"],
            },
        ),
        (
            "chrome_headed",
            {
                "headless": False,
                "channel": "chrome",
                "args": ["--disable-blink-features=AutomationControlled"],
            },
        ),
    ]
    for label, kwargs in strategies:
        if await try_launch(label, kwargs):
            break


if __name__ == "__main__":
    asyncio.run(main())
