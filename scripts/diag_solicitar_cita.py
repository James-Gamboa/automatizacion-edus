"""Login, open Solicitar Cita, select MEDICINA, dump DOM for especialidad."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edus.booking import click_agregar_cita_titular, select_servicio
from edus.browser import open_browser, wait_ajax
from edus.config import load_settings
from edus.constants import SPECIALTY_PRESETS
from edus.logging_setup import setup_logging
from edus.login import login


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    preset = SPECIALTY_PRESETS["medicina_general"]
    async with open_browser(settings) as (_b, _c, page):
        # headed for debug
        await login(page, settings)
        await click_agregar_cita_titular(page, settings)
        try:
            await select_servicio(page, preset, settings)
        except Exception as exc:
            print("select_servicio error:", exc)
        await wait_ajax(page, 2.0)
        dump = await page.evaluate(
            """() => {
                const nodes = Array.from(document.querySelectorAll('[id*="ervicio"], [id*="special"], [id*="Especial"], [id*="menu"]'));
                const ids = nodes.map((n) => ({
                    id: n.id,
                    tag: n.tagName,
                    text: ((n.textContent || '').trim()).slice(0, 80),
                    value: n.value || null,
                    optionCount: n.options ? n.options.length : null,
                })).filter((x) => x.id);
                const selects = Array.from(document.querySelectorAll('select')).map((s) => ({
                    id: s.id,
                    name: s.name,
                    options: Array.from(s.options).slice(0, 15).map((o) => ({v:o.value, t:(o.textContent||'').trim()})),
                }));
                return { ids: ids.slice(0, 80), selects: selects.slice(0, 20) };
            }"""
        )
        out = ROOT / "logs" / "dom_solicitar_cita.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Wrote", out)
        print(json.dumps(dump, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    asyncio.run(main())
