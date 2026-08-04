"""Post-login booking flow (official guide Phase 3)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from playwright.async_api import Page

from edus.browser import wait_ajax
from edus.config import Settings
from edus.constants import (
    BTN_ADD_CITA,
    COMMON_ERRORS,
    MENU_ESPECIALIDADES,
    MENU_SERVICIOS,
    SpecialtyPreset,
    TABLA_CITAS,
    TABLA_CUPOS,
)
from edus.time_rules import is_slot_within_booking_window

logger = logging.getLogger("edus.booking")


@dataclass
class Slot:
    fecha: str
    hora: str
    numero: str
    consultorio: str
    funcionario: str
    row_index: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "fecha": self.fecha,
            "hora": self.hora,
            "numero": self.numero,
            "consultorio": self.consultorio,
            "funcionario": self.funcionario,
            "row_index": self.row_index,
        }


async def click_agregar_cita_titular(page: Page, settings: Settings) -> None:
    """PrimeFaces AJAX: PrimeFaces.ab({s: 'formSIAC:btnMenuAdd', f: 'formSIAC'});"""
    clicked = await page.evaluate(
        """(btnId) => {
            if (typeof PrimeFaces !== 'undefined' && PrimeFaces.ab) {
                PrimeFaces.ab({s: btnId, f: 'formSIAC'});
                return 'primefaces';
            }
            const el = document.getElementById(btnId);
            if (el) {
                el.click();
                return 'dom';
            }
            const nodes = Array.from(document.querySelectorAll('a, button, span'));
            const target = nodes.find((n) => (n.textContent || '').trim() === 'Agregar una cita');
            if (target) {
                target.click();
                return 'text';
            }
            return null;
        }""",
        BTN_ADD_CITA,
    )
    if not clicked:
        raise RuntimeError("Could not click 'Agregar una cita' (titular)")
    logger.info("Opened add-cita form via %s", clicked)
    await wait_ajax(page, max(settings.ajax_wait_seconds, 3.5))
    # Wait for Solicitar Cita form (Servicio dropdown)
    try:
        await page.wait_for_function(
            """() => !!document.getElementById('formSIAC:menuServicios_input')
                 || !!document.getElementById('formSIAC:menuServicios_label')""",
            timeout=20000,
        )
    except Exception as exc:
        raise RuntimeError("Solicitar Cita form did not load (Servicio dropdown missing)") from exc


async def _select_primefaces_menu(
    page: Page,
    input_id: str,
    *,
    code: str,
    labels: list[str],
    wait_seconds: float,
) -> str:
    """
    Select a PrimeFaces selectOneMenu via real UI clicks (Playwright locators).
    Setting only the hidden _input leaves the visible label empty.
    """
    select_id = input_id.replace("_input", "")
    label_id = f"{select_id}_label"
    panel_id = f"{select_id}_panel"

    # Escape JSF colons for CSS selectors
    def css_id(raw: str) -> str:
        return "#" + raw.replace(":", "\\:")

    # When reading options from underlying select, use *_input (actual <select>)
    meta = await page.evaluate(
        """([selectId, code, labels]) => {
            const normalize = (s) => (s || '').toUpperCase().normalize('NFD')
                .replace(/[\\u0300-\\u036f]/g, '').trim();
            const needles = (labels || []).map(normalize).filter(Boolean);
            const select =
                document.getElementById(selectId + '_input')
                || document.getElementById(selectId)
                || document.querySelector('select[id*=\"' + selectId.split(':').pop() + '\"]');
            const options = (select && select.options) ? Array.from(select.options) : [];
            let match = null;
            if (code) {
                match = options.find((o) => String(o.value) === String(code) && String(o.value) !== '' && String(o.value) !== '-1');
            }
            if (!match && needles.length) {
                match = options.find((o) => {
                    const t = normalize(o.textContent);
                    if (!t || t.includes('SELECCIONE')) return false;
                    return needles.some((n) => t === n || t.includes(n));
                });
            }
            return {
                optionTexts: options.map((o) => (o.textContent || '').trim()),
                matchText: match ? (match.textContent || '').trim() : '',
                matchValue: match ? String(match.value) : '',
                needles,
            };
        }""",
        [select_id, code or "", labels],
    )

    search_texts = []
    if meta.get("matchText"):
        search_texts.append(meta["matchText"])
    search_texts.extend(labels or [])

    label = page.locator(css_id(label_id))
    await label.wait_for(state="visible", timeout=15000)
    await label.click()
    await wait_ajax(page, 0.6)

    panel = page.locator(css_id(panel_id))
    try:
        await panel.wait_for(state="visible", timeout=5000)
    except Exception:
        # Retry open
        await label.click()
        await wait_ajax(page, 0.8)
        await panel.wait_for(state="visible", timeout=5000)

    clicked_text = None
    for text in search_texts:
        if not text:
            continue
        # Exact then contains
        item = panel.locator("li, .ui-selectonemenu-item").filter(has_text=text)
        count = await item.count()
        if count == 0:
            # Case-insensitive contains via JS fallback below
            continue
        await item.first.click()
        clicked_text = text
        break

    if not clicked_text:
        # JS fallback: click by normalized needle
        clicked_text = await page.evaluate(
            """([panelId, labels]) => {
                const normalize = (s) => (s || '').toUpperCase().normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '').trim();
                const needles = (labels || []).map(normalize);
                const panel = document.getElementById(panelId) || document;
                const items = Array.from(panel.querySelectorAll('li, .ui-selectonemenu-item'));
                for (const el of items) {
                    const t = normalize(el.textContent);
                    if (!t || t.includes('SELECCIONE')) continue;
                    if (needles.some((n) => t === n || t.includes(n))) {
                        el.click();
                        return (el.textContent || '').trim();
                    }
                }
                return null;
            }""",
            [panel_id, labels],
        )

    if not clicked_text:
        raise RuntimeError(
            f"Could not find option for {select_id}. "
            f"labels={labels} options={meta.get('optionTexts')} "
            f"needles={meta.get('needles')}"
        )

    # Force change/AJAX after UI click
    await page.evaluate(
        """([selectId, valueHint]) => {
            const select = document.getElementById(selectId);
            const input = document.getElementById(selectId + '_input');
            if (select && valueHint) {
                const opt = Array.from(select.options || []).find(
                    (o) => String(o.value) === String(valueHint)
                        || (o.textContent || '').trim().toUpperCase().includes(String(valueHint).toUpperCase())
                );
                if (opt) {
                    select.value = opt.value;
                    if (input) input.value = opt.value;
                }
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (typeof PrimeFaces !== 'undefined' && PrimeFaces.ab) {
                try { PrimeFaces.ab({s: selectId, e: 'valueChange', f: 'formSIAC', p: selectId}); }
                catch (e) {
                    try { PrimeFaces.ab({s: selectId, f: 'formSIAC'}); } catch (e2) {}
                }
            }
        }""",
        [select_id, meta.get("matchValue") or clicked_text],
    )

    await wait_ajax(page, wait_seconds)

    visible = ""
    try:
        visible = (await label.inner_text()).strip()
    except Exception:
        visible = str(clicked_text)

    logger.info(
        "Selected %s via ui_click => %s (visible=%r)",
        select_id,
        clicked_text,
        visible,
    )
    if not visible or "SELECCIONE" in visible.upper():
        raise RuntimeError(
            f"Visible label for {select_id} still empty/placeholder after select: {visible!r}"
        )
    return visible


async def _especialidad_options_ready(page: Page) -> bool:
    """True when Especialidad <select> (_input) has real options after Servicio AJAX."""
    return bool(
        await page.evaluate(
            """() => {
                // PrimeFaces: root is DIV; real <select> is *_input
                const select =
                    document.getElementById('formSIAC:menuEspecialidades_input')
                    || document.querySelector('select[id*=\"menuEspecialidades\"]');
                const label = document.getElementById('formSIAC:menuEspecialidades_label');
                const labelText = ((label && label.textContent) || '').trim().toUpperCase();

                if (select && select.options) {
                    const opts = Array.from(select.options).filter((o) => {
                        const t = (o.textContent || '').trim().toUpperCase();
                        const v = String(o.value || '');
                        return v && v !== '-1' && v !== '' && !t.includes('SELECCIONE');
                    });
                    if (opts.length > 0) return true;
                }

                const panel = document.getElementById('formSIAC:menuEspecialidades_panel');
                if (panel) {
                    const items = Array.from(panel.querySelectorAll('li, .ui-selectonemenu-item'))
                        .map((el) => (el.textContent || '').trim().toUpperCase())
                        .filter((t) => t && !t.includes('SELECCIONE'));
                    if (items.length > 0) return true;
                }

                if (labelText && !labelText.includes('SELECCIONE')) return true;
                return false;
            }"""
        )
    )


async def select_servicio(page: Page, preset: SpecialtyPreset, settings: Settings) -> str:
    """Step 1 of Solicitar Cita: Servicio dropdown (MEDICINA | ODONTOLOGIA)."""
    await wait_ajax(page, 0.8)
    selected = await _select_primefaces_menu(
        page,
        MENU_SERVICIOS,
        code=preset.get("servicio_code", ""),
        labels=preset.get("servicio_labels", []),
        wait_seconds=max(settings.ajax_wait_seconds, 4.0),
    )
    for i in range(40):
        if await _especialidad_options_ready(page):
            logger.info("Especialidad options ready after %.1fs", (i + 1) * 0.5)
            return selected
        await wait_ajax(page, 0.5)

    diag = await page.evaluate(
        """() => {
            const sLabel = document.getElementById('formSIAC:menuServicios_label');
            const eLabel = document.getElementById('formSIAC:menuEspecialidades_label');
            const es = document.getElementById('formSIAC:menuEspecialidades');
            const opts = (es && es.options) ? Array.from(es.options).slice(0, 12).map(
                (o) => ({ v: o.value, t: (o.textContent || '').trim() })
            ) : [];
            return {
                servicioLabel: sLabel ? (sLabel.textContent || '').trim() : null,
                especialidadLabel: eLabel ? (eLabel.textContent || '').trim() : null,
                optionCount: (es && es.options) ? es.options.length : -1,
                options: opts,
                bodySnippet: ((document.body && document.body.innerText) || '').slice(0, 400),
            };
        }"""
    )
    raise RuntimeError(
        "After selecting Servicio, Especialidad options did not load "
        f"(still on SELECCIONE ESPECIALIDAD...). diag={diag}"
    )


async def select_especialidad(page: Page, preset: SpecialtyPreset, settings: Settings) -> str:
    """Step 2 of Solicitar Cita: Especialidad (depends on Servicio)."""
    if not await _especialidad_options_ready(page):
        raise RuntimeError(
            "Especialidad dropdown has no options yet — select Servicio (MEDICINA/ODONTOLOGIA) first"
        )
    return await _select_primefaces_menu(
        page,
        MENU_ESPECIALIDADES,
        code=preset.get("especialidad_code", ""),
        labels=preset.get("especialidad_labels", []),
        wait_seconds=max(settings.ajax_wait_seconds, 3.0),
    )


async def read_page_errors(page: Page) -> list[str]:
    text = await page.inner_text("body")
    found = []
    for needle, code in COMMON_ERRORS.items():
        if needle.lower() in text.lower():
            found.append(f"{code}: {needle}")
    return found


async def parse_cupos(page: Page) -> list[Slot]:
    rows = await page.evaluate(
        """(tableId) => {
            const table = document.getElementById(tableId);
            if (!table) return [];
            const trs = table.querySelectorAll('tbody tr');
            const out = [];
            trs.forEach((tr, idx) => {
                const cells = Array.from(tr.querySelectorAll('td')).map(
                    (td) => (td.textContent || '').trim().replace(/\\s+/g, ' ')
                );
                if (!cells.length) return;
                const joined = cells.join(' ').toLowerCase();
                if (joined.includes('no se encontraron') || joined.includes('sin registro')) return;
                if (joined.includes('gestionó todas') || joined.includes('gestiono todas')) return;
                out.push({
                    fecha: cells[0] || '',
                    hora: cells[1] || '',
                    numero: cells[2] || '',
                    consultorio: cells[3] || '',
                    funcionario: cells[4] || '',
                    row_index: idx,
                });
            });
            return out;
        }""",
        TABLA_CUPOS,
    )
    slots = [Slot(**row) for row in rows]
    logger.info("Parsed %s cupo rows", len(slots))
    return slots


async def has_existing_appointment_same_day(page: Page, fecha: str) -> bool:
    """Avoid duplicate reservations by checking existing appointments table."""
    if not fecha:
        return False
    # Normalize date fragments
    date_token = fecha.strip()
    exists = await page.evaluate(
        """([tableId, fecha]) => {
            const table = document.getElementById(tableId);
            const root = table || document.body;
            const text = (root.textContent || '');
            return text.includes(fecha);
        }""",
        [TABLA_CITAS, date_token],
    )
    return bool(exists)


def filter_slots(
    slots: list[Slot],
    settings: Settings,
) -> tuple[list[Slot], list[Slot]]:
    """Return (bookable_in_window, out_of_window_or_excluded)."""
    in_window: list[Slot] = []
    out_window: list[Slot] = []
    excluded = {d.strip() for d in settings.excluir_fechas}

    for slot in slots:
        if any(ex and ex in slot.fecha for ex in excluded):
            out_window.append(slot)
            continue
        if settings.enforce_slot_window:
            if is_slot_within_booking_window(
                slot.hora, start=settings.slot_start, end=settings.slot_end
            ):
                in_window.append(slot)
            else:
                out_window.append(slot)
        else:
            in_window.append(slot)
    return in_window, out_window


async def book_slot(page: Page, slot: Slot, settings: Settings) -> bool:
    """Click Ver cita on row, then Confirmar."""
    if settings.dry_run:
        logger.info("DRY RUN — would book slot %s", slot.as_dict())
        return True

    opened = await page.evaluate(
        """([tableId, rowIndex]) => {
            const table = document.getElementById(tableId);
            if (!table) return false;
            const tr = table.querySelectorAll('tbody tr')[rowIndex];
            if (!tr) return false;
            const candidates = Array.from(tr.querySelectorAll('a, button, span, input'));
            const btn = candidates.find((el) => {
                const t = (el.textContent || el.value || '').trim().toLowerCase();
                return t.includes('ver cita') || t.includes('seleccionar') || el.getAttribute('onclick');
            });
            if (!btn) return false;
            btn.click();
            return true;
        }""",
        [TABLA_CUPOS, slot.row_index],
    )
    if not opened:
        raise RuntimeError(f"Could not open Ver cita for row {slot.row_index}")

    await wait_ajax(page, settings.ajax_wait_seconds)

    confirmed = await page.evaluate(
        """() => {
            const nodes = Array.from(document.querySelectorAll('a, button, span, input'));
            const btn = nodes.find((el) => {
                const t = (el.textContent || el.value || '').trim().toLowerCase();
                return t === 'confirmar' || t.includes('confirmar cita') || t === 'aceptar';
            });
            if (!btn) return false;
            btn.click();
            return true;
        }"""
    )
    await wait_ajax(page, settings.ajax_wait_seconds)

    if not confirmed:
        # Some dialogs use PrimeFaces button with id containing confirm
        confirmed = await page.evaluate(
            """() => {
                const btn = document.querySelector('[id*=\"confirm\" i], [id*=\"Confirmar\"]');
                if (!btn) return false;
                btn.click();
                return true;
            }"""
        )
        await wait_ajax(page, 2.0)

    errors = await read_page_errors(page)
    if any("slot_taken" in e or "duplicate" in e for e in errors):
        logger.warning("Booking rejected by EDUS: %s", errors)
        return False

    body = await page.inner_text("body")
    success_hints = [
        "cita asignada",
        "cita reservada",
        "se ha agendado",
        "cita confirmada",
        "exitosamente",
        "éxito",
    ]
    if any(h in body.lower() for h in success_hints) or confirmed:
        logger.info("Booking confirmation submitted for %s %s", slot.fecha, slot.hora)
        return True
    logger.warning("Could not verify booking confirmation text")
    return bool(confirmed)


async def ensure_centro_salud_note(page: Page, settings: Settings) -> Optional[str]:
    """
    After login, EDUS uses the insured's assigned health center.
    If CENTRO_SALUD is set, verify it appears on the page (notify if mismatch).
    """
    if not settings.centro_salud:
        return None
    text = await page.inner_text("body")
    needle = settings.centro_salud.strip()
    if re.search(re.escape(needle), text, flags=re.IGNORECASE):
        logger.info("Configured health center found on page: %s", needle)
        return needle
    logger.warning(
        "Configured CENTRO_SALUD '%s' not found on page text; continuing with assigned center",
        needle,
    )
    return None
