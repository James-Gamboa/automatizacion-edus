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
            // fallback: find link by text
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


async def _select_by_code_or_label(
    page: Page,
    input_id: str,
    *,
    code: str,
    labels: list[str],
    wait_seconds: float,
) -> str:
    result = await page.evaluate(
        """([inputId, code, labels]) => {
            const input = document.getElementById(inputId);
            if (!input) throw new Error('Select input not found: ' + inputId);

            const selectId = inputId.replace(/_input$/, '');
            let select = document.getElementById(selectId);
            // PrimeFaces often uses a hidden select sibling
            if (!select || select.tagName !== 'SELECT') {
                select = document.querySelector('select[name=\"' + inputId.replace('_input','') + '\"]')
                      || document.querySelector('select[id=\"' + selectId + '\"]')
                      || input.closest('div')?.querySelector('select')
                      || null;
            }

            const normalize = (s) => (s || '').toUpperCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            const labelNeedles = (labels || []).map(normalize);

            let chosenValue = null;
            let chosenText = null;

            const options = select ? Array.from(select.options) : [];
            if (code) {
                const byCode = options.find((o) => String(o.value) === String(code));
                if (byCode) {
                    chosenValue = byCode.value;
                    chosenText = byCode.textContent;
                }
            }
            if (!chosenValue && labelNeedles.length) {
                const byLabel = options.find((o) => {
                    const t = normalize(o.textContent);
                    return labelNeedles.some((n) => t.includes(n));
                });
                if (byLabel) {
                    chosenValue = byLabel.value;
                    chosenText = byLabel.textContent;
                }
            }

            // Also try panel list items (PrimeFaces selectOneMenu)
            if (!chosenValue) {
                const panel = document.getElementById(selectId + '_panel')
                    || document.querySelector('[id=\"' + selectId + '_panel\"]');
                // Open menu
                const trigger = document.getElementById(selectId + '_label')
                    || document.querySelector('[id=\"' + selectId + '_label\"]')
                    || input;
                if (trigger) trigger.click();
            }

            if (chosenValue != null) {
                input.value = chosenValue;
                if (select) {
                    select.value = chosenValue;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
                input.dispatchEvent(new Event('change', { bubbles: true }));
                // Trigger PrimeFaces ajax if present
                if (typeof PrimeFaces !== 'undefined') {
                    try {
                        const widget = Object.values(PrimeFaces.widgets || {}).find(
                            (w) => w && w.id === selectId
                        );
                        if (widget && widget.selectValue) {
                            widget.selectValue(chosenValue);
                        }
                    } catch (e) {}
                }
                return { ok: true, value: chosenValue, text: (chosenText || '').trim() };
            }
            return {
                ok: false,
                options: options.map((o) => ({ value: o.value, text: (o.textContent || '').trim() })),
            };
        }""",
        [input_id, code or "", labels],
    )

    if not result.get("ok"):
        # Second pass: open PF menu and click item by label
        clicked = await page.evaluate(
            """([inputId, labels]) => {
                const selectId = inputId.replace(/_input$/, '');
                const normalize = (s) => (s || '').toUpperCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                const needles = (labels || []).map(normalize);
                const trigger = document.getElementById(selectId + '_label')
                    || document.querySelector('label[id=\"' + selectId + '_label\"]')
                    || document.getElementById(inputId);
                if (trigger) trigger.click();
                const items = Array.from(document.querySelectorAll('li, .ui-selectonemenu-item, td'));
                for (const item of items) {
                    const t = normalize(item.textContent);
                    if (needles.some((n) => t.includes(n))) {
                        item.click();
                        return (item.textContent || '').trim();
                    }
                }
                return null;
            }""",
            [input_id, labels],
        )
        await wait_ajax(page, wait_seconds)
        if clicked:
            logger.info("Selected %s via menu label: %s", input_id, clicked)
            return str(clicked)
        options = result.get("options") or []
        raise RuntimeError(
            f"Could not select option for {input_id} (code={code}, labels={labels}). "
            f"Available: {options[:20]}"
        )

    await wait_ajax(page, wait_seconds)
    logger.info("Selected %s => %s (%s)", input_id, result.get("text"), result.get("value"))
    return str(result.get("text") or result.get("value"))


async def select_servicio(page: Page, preset: SpecialtyPreset, settings: Settings) -> str:
    return await _select_by_code_or_label(
        page,
        MENU_SERVICIOS,
        code=preset.get("servicio_code", ""),
        labels=preset.get("servicio_labels", []),
        wait_seconds=settings.ajax_wait_seconds,
    )


async def select_especialidad(page: Page, preset: SpecialtyPreset, settings: Settings) -> str:
    return await _select_by_code_or_label(
        page,
        MENU_ESPECIALIDADES,
        code=preset.get("especialidad_code", ""),
        labels=preset.get("especialidad_labels", []),
        wait_seconds=settings.ajax_wait_seconds,
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
