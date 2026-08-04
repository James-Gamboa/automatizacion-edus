"""EDUS login with CAPTCHA OCR retries (official guide Phase 2)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from playwright.async_api import Page

from edus.browser import wait_ajax
from edus.captcha import (
    CaptchaDownloadError,
    captcha_field_present,
    download_captcha,
    looks_like_waf_rejection,
    ocr_captcha,
    refresh_captcha_image,
)
from edus.config import Settings
from edus.constants import (
    LOGIN_CAPTCHA,
    LOGIN_ID_TYPE,
    LOGIN_PASS,
    LOGIN_SUBMIT,
    LOGIN_SUCCESS_MARKER,
    LOGIN_USER,
)

logger = logging.getLogger("edus.login")


class WafRejectedError(RuntimeError):
    """EDUS/F5 WAF blocked this client (Request Rejected)."""


async def _set_input_value(page: Page, element_id: str, value: str) -> None:
    await page.evaluate(
        """([id, value]) => {
            const el = document.getElementById(id);
            if (!el) throw new Error('Element not found: ' + id);
            el.focus();
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [element_id, value],
    )


async def _click_id(page: Page, element_id: str) -> None:
    await page.evaluate(
        """(id) => {
            const el = document.getElementById(id);
            if (!el) throw new Error('Element not found: ' + id);
            el.click();
        }""",
        element_id,
    )


async def _set_id_type(page: Page, tip: str) -> None:
    exists = await page.evaluate(
        """(id) => !!document.getElementById(id)""",
        LOGIN_ID_TYPE,
    )
    if not exists:
        return
    await page.evaluate(
        """([id, value]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.value = value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [LOGIN_ID_TYPE, tip],
    )


async def is_logged_in(page: Page) -> bool:
    html = await page.content()
    return LOGIN_SUCCESS_MARKER in html


async def assert_not_waf_blocked(page: Page) -> None:
    html = await page.content()
    if looks_like_waf_rejection(html):
        raise WafRejectedError(
            "EDUS WAF rejected this client (Request Rejected). "
            "Your IP was likely rate-limited after rapid retries. "
            "Wait 15–30 minutes, then retry with --headed and fewer attempts."
        )


async def wait_for_login_form(page: Page, settings: Settings, *, navigate: bool = True) -> None:
    """EDUS sits behind a JS bot challenge (TSPD); wait until the JSF login form appears."""
    if navigate:
        await page.goto(settings.base_url, wait_until="commit")
    await wait_ajax(page, 1.5)
    await assert_not_waf_blocked(page)
    try:
        await page.wait_for_function(
            """() => !!document.getElementById('formInicioSesion')
                 || !!document.getElementById('formInicioSesion:usuario')
                 || (document.body && document.body.innerText.includes('Agregar una cita'))""",
            timeout=settings.navigation_timeout_ms,
        )
    except Exception as exc:
        await assert_not_waf_blocked(page)
        html_len = len(await page.content())
        raise RuntimeError(
            f"Login form did not appear after bot challenge (html_len={html_len}). "
            "Try --headed or increase EDUS_NAVIGATION_TIMEOUT_MS."
        ) from exc
    await assert_not_waf_blocked(page)
    await wait_ajax(page, 1.0)


async def login(page: Page, settings: Settings) -> None:
    """Login with CAPTCHA OCR retries. Full page reload each attempt (official guide)."""
    max_attempts = max(1, settings.captcha_max_attempts)
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        logger.info("Login attempt %s/%s", attempt, max_attempts)
        try:
            # Guide: each attempt reloads the page for a fresh CAPTCHA
            await wait_for_login_form(page, settings, navigate=True)

            if await is_logged_in(page):
                logger.info("Already logged in")
                return

            html = await page.content()
            await assert_not_waf_blocked(page)
            needs_captcha = captcha_field_present(html)
            captcha_text = ""

            if needs_captcha:
                with tempfile.TemporaryDirectory(prefix="edus_login_") as tmp:
                    captcha_path = Path(tmp) / "captcha.png"
                    try:
                        await download_captcha(page, captcha_path)
                        captcha_text = ocr_captcha(
                            captcha_path, tesseract_cmd=settings.tesseract_cmd
                        )
                    except CaptchaDownloadError as exc:
                        last_error = str(exc)
                        logger.warning("CAPTCHA download failed on attempt %s: %s", attempt, exc)
                        if "WAF" in last_error or "Request Rejected" in last_error:
                            raise WafRejectedError(last_error) from exc
                        await wait_ajax(page, min(5.0, 1.5 + attempt * 0.3))
                        continue
                    except Exception as exc:
                        last_error = str(exc)
                        logger.warning("OCR failed on attempt %s: %s", attempt, exc)
                        await wait_ajax(page, 1.5)
                        continue
                if not captcha_text or len(captcha_text) < 4:
                    logger.warning(
                        "Empty/short OCR result on attempt %s (%r)", attempt, captcha_text
                    )
                    await wait_ajax(page, 1.5 + (attempt % 3) * 0.5)
                    continue
                logger.info("OCR candidate=%r length=%s", captcha_text, len(captcha_text))
            else:
                logger.info("CAPTCHA field not present; submitting without OCR")

            await _set_id_type(page, settings.tip_identificacion)
            await _set_input_value(page, LOGIN_USER, settings.cedula)
            await _set_input_value(page, LOGIN_PASS, settings.clave)
            if needs_captcha:
                captcha_exists = await page.evaluate(
                    """(id) => !!document.getElementById(id)""",
                    LOGIN_CAPTCHA,
                )
                if captcha_exists:
                    await _set_input_value(page, LOGIN_CAPTCHA, captcha_text)

            await _click_id(page, LOGIN_SUBMIT)
            await wait_ajax(page, settings.ajax_wait_seconds)
            try:
                await page.wait_for_function(
                    """() => {
                        const body = (document.body && document.body.innerText) || '';
                        return body.includes('Agregar una cita')
                            || /captcha|incorrect|inv[aá]lid/i.test(body)
                            || !!document.getElementById('formInicioSesion');
                    }""",
                    timeout=15000,
                )
            except Exception:
                pass

            await assert_not_waf_blocked(page)

            if await is_logged_in(page):
                logger.info("Login successful on attempt %s", attempt)
                return

            page_text = await page.inner_text("body")
            if (
                "incorrect" in page_text.lower()
                or "inválid" in page_text.lower()
                or "invalida" in page_text.lower()
                or "captcha" in page_text.lower()
            ):
                last_error = "Invalid credentials or CAPTCHA"
            else:
                last_error = "Login not confirmed (marker missing)"
            logger.warning("Login attempt %s failed: %s", attempt, last_error)
            # Brief pause before next full reload (reduces WAF pressure a bit)
            await wait_ajax(page, 1.5 + (attempt % 4) * 0.4)

        except WafRejectedError:
            raise
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Login attempt %s error: %s", attempt, exc)
            await wait_ajax(page, min(8.0, 2.0 + attempt * 0.4))

    raise RuntimeError(
        f"Login failed after {max_attempts} attempts. Last error: {last_error}"
    )
