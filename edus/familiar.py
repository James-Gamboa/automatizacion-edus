"""Grupo familiar navigation (official guide Phase 4)."""

from __future__ import annotations

import logging

from playwright.async_api import Page

from edus.browser import wait_ajax
from edus.config import Settings

logger = logging.getLogger("edus.familiar")


async def click_ver_citas_familiar(page: Page, settings: Settings) -> bool:
    """Click 'Ver Citas' for the configured family member."""
    fam_nombre = settings.familiar_nombre.strip()
    fam_cedula = settings.familiar_cedula.strip()
    if not fam_nombre and not fam_cedula:
        return False

    if fam_nombre:
        search = fam_nombre.upper()
        clicked = await page.evaluate(
            """(searchTerm) => {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while ((node = walker.nextNode())) {
                    const txt = (node.textContent || '').trim();
                    if (txt.toUpperCase().includes(searchTerm) && node.children.length === 0) {
                        // climb to row and find Ver Citas
                        let row = node;
                        for (let i = 0; i < 8 && row; i++) {
                            const links = row.querySelectorAll('a, button, span, td');
                            for (const el of links) {
                                const t = (el.textContent || '').trim();
                                if (t === 'Ver Citas' || t === 'Ver citas') {
                                    el.click();
                                    return true;
                                }
                            }
                            row = row.parentElement;
                        }
                    }
                }
                return false;
            }""",
            search,
        )
    else:
        clicked = await page.evaluate(
            """(cedula) => {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while ((node = walker.nextNode())) {
                    const txt = (node.textContent || '').trim();
                    if (txt.includes(cedula) && node.children.length === 0) {
                        let row = node;
                        for (let i = 0; i < 8 && row; i++) {
                            const links = row.querySelectorAll('a, button, span, td');
                            for (const el of links) {
                                const t = (el.textContent || '').trim();
                                if (t === 'Ver Citas' || t === 'Ver citas') {
                                    el.click();
                                    return true;
                                }
                            }
                            row = row.parentElement;
                        }
                    }
                }
                return false;
            }""",
            fam_cedula,
        )

    if clicked:
        logger.info("Opened family member appointments view")
        await wait_ajax(page, 3.0)
    else:
        logger.warning("Could not find Ver Citas for family member")
    return bool(clicked)


async def click_agregar_cita_familiar(page: Page, settings: Settings) -> bool:
    """
    Click the 'Agregar una cita' button that appears AFTER the family member
    name/cedula in the DOM (guide Phase 4). Python conditions resolved before JS.
    """
    fam_nombre = settings.familiar_nombre.strip()
    fam_cedula = settings.familiar_cedula.strip()

    if fam_nombre:
        search_term = fam_nombre.upper()
        clicked = await page.evaluate(
            """(searchTerm) => {
                let seen = false;
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while ((node = walker.nextNode())) {
                    const txt = (node.textContent || '').trim();
                    if (txt.toUpperCase().includes(searchTerm) && node.children.length === 0) {
                        seen = true;
                        continue;
                    }
                    if (
                        seen &&
                        txt === 'Agregar una cita' &&
                        (node.tagName === 'A' || node.tagName === 'BUTTON' || node.getAttribute('onclick'))
                    ) {
                        node.click();
                        return true;
                    }
                }
                return false;
            }""",
            search_term,
        )
    elif fam_cedula:
        clicked = await page.evaluate(
            """(cedula) => {
                let seen = false;
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while ((node = walker.nextNode())) {
                    const txt = (node.textContent || '').trim();
                    if (txt.includes(cedula) && node.children.length === 0) {
                        seen = true;
                        continue;
                    }
                    if (
                        seen &&
                        txt === 'Agregar una cita' &&
                        (node.tagName === 'A' || node.tagName === 'BUTTON' || node.getAttribute('onclick'))
                    ) {
                        node.click();
                        return true;
                    }
                }
                return false;
            }""",
            fam_cedula,
        )
    else:
        return False

    if clicked:
        logger.info("Clicked Agregar una cita for family member")
        await wait_ajax(page, 4.0)
    return bool(clicked)


async def switch_to_familiar(page: Page, settings: Settings) -> None:
    if not settings.familiar_cedula and not settings.familiar_nombre:
        return
    await click_ver_citas_familiar(page, settings)
    ok = await click_agregar_cita_familiar(page, settings)
    if not ok:
        raise RuntimeError(
            "Failed to open 'Agregar una cita' for the configured family member"
        )
