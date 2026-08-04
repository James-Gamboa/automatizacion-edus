"""CAPTCHA download + OCR following the official EDUS guide."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance

from edus.constants import CAPTCHA_PATH

logger = logging.getLogger("edus.captcha")

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
GIF_MAGIC = b"GIF8"


class CaptchaDownloadError(RuntimeError):
    """Raised when CAPTCHA bytes are not a usable image."""


def resolve_tesseract_cmd(configured: str = "") -> Optional[str]:
    if configured:
        path = Path(configured)
        if path.exists():
            return str(path)
    which = shutil.which("tesseract")
    if which:
        return which
    windows_candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for candidate in windows_candidates:
        if candidate.exists():
            return str(candidate)
    return None


def is_image_bytes(body: bytes) -> bool:
    if not body or len(body) < 100:
        return False
    return (
        body.startswith(PNG_MAGIC)
        or body.startswith(JPEG_MAGIC)
        or body.startswith(GIF_MAGIC)
    )


def looks_like_waf_rejection(body: bytes | str) -> bool:
    text = body.decode("utf-8", errors="ignore") if isinstance(body, bytes) else body
    lowered = text.lower()
    return (
        "request rejected" in lowered
        or "support id" in lowered
        or "the requested url was rejected" in lowered
    )


def preprocess_captcha(image_path: Path, output_path: Path) -> Path:
    img = Image.open(image_path).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    width, height = img.size
    img = img.resize((width * 3, height * 3), Image.LANCZOS)
    img.save(output_path)
    return output_path


def ocr_captcha(image_path: Path, *, tesseract_cmd: str = "") -> str:
    tess = resolve_tesseract_cmd(tesseract_cmd)
    if not tess:
        raise RuntimeError(
            "tesseract not found. Install Tesseract OCR and optionally set TESSERACT_CMD."
        )
    if not is_image_bytes(image_path.read_bytes()):
        raise CaptchaDownloadError(f"Not a valid image file: {image_path}")

    with tempfile.TemporaryDirectory(prefix="edus_captcha_") as tmp:
        processed = Path(tmp) / "captcha_processed.png"
        preprocess_captcha(image_path, processed)
        result = subprocess.run(
            [
                tess,
                str(processed),
                "-",
                "--psm",
                "7",
                "-c",
                "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        raw = (result.stdout or "").strip()
        cleaned = re.sub(r"[^A-Za-z0-9]", "", raw)
        logger.debug("OCR raw=%r cleaned=%r", raw, cleaned)
        return cleaned


async def _collect_captcha_urls(page) -> list[str]:
    urls: list[str] = []
    try:
        discovered = await page.evaluate(
            """() => {
                const out = [];
                for (const img of document.images) {
                    const src = img.currentSrc || img.src || '';
                    if (!src) continue;
                    const hay = (src + ' ' + (img.id || '') + ' ' + (img.alt || '')).toLowerCase();
                    if (hay.includes('captcha') || (img.naturalWidth >= 150 && img.naturalHeight >= 40 && img.naturalWidth <= 400)) {
                        out.push(src);
                    }
                }
                // common EDUS markup: img next to captcha field
                const input = document.getElementById('formInicioSesion:captchaDigitado');
                if (input) {
                    const root = input.closest('table, tr, div, form') || document;
                    for (const img of root.querySelectorAll('img')) {
                        if (img.src) out.push(img.src);
                    }
                }
                try {
                    out.push(new URL('/CitasWebPF/captcha', location.origin).href);
                    out.push(new URL('/CitasWebPF/captcha?', location.origin).href + Date.now());
                } catch (e) {}
                return [...new Set(out)];
            }"""
        )
        urls.extend(discovered or [])
    except Exception as exc:
        logger.debug("Could not discover captcha URLs from DOM: %s", exc)

    origin = "https://edus.ccss.sa.cr"
    try:
        origin = await page.evaluate("() => location.origin") or origin
    except Exception:
        pass
    urls.extend(
        [
            f"{origin}{CAPTCHA_PATH}",
            f"{origin}/CitasWebPF/captcha",
            f"https://edus.ccss.sa.cr/CitasWebPF/captcha",
        ]
    )
    # de-dupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


async def download_captcha(page, dest: Path) -> Path:
    """Download CAPTCHA via HTTP with session cookies (not screenshot)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    candidates = await _collect_captcha_urls(page)
    last_error = "no candidates"

    for url in candidates:
        try:
            response = await page.request.get(url, timeout=30000)
        except Exception as exc:
            last_error = str(exc)
            continue
        body = await response.body()
        ctype = (response.headers.get("content-type") or "").lower()
        if looks_like_waf_rejection(body):
            raise CaptchaDownloadError(
                "EDUS WAF rejected the CAPTCHA request (Request Rejected). "
                "Wait 15–30 minutes before retrying; avoid rapid retries."
            )
        if not response.ok:
            last_error = f"HTTP {response.status} for {url}"
            continue
        if "html" in ctype or not is_image_bytes(body):
            last_error = (
                f"Non-image CAPTCHA body from {url} "
                f"(status={response.status}, ctype={ctype!r}, len={len(body)})"
            )
            logger.warning(last_error)
            continue
        dest.write_bytes(body)
        logger.info("CAPTCHA downloaded to %s (%s bytes) from %s", dest, len(body), url)
        return dest

    raise CaptchaDownloadError(f"Failed to download a valid CAPTCHA image: {last_error}")


async def refresh_captcha_image(page) -> None:
    """Refresh CAPTCHA without a full navigation (avoids re-triggering WAF)."""
    clicked = await page.evaluate(
        """() => {
            const nodes = Array.from(document.querySelectorAll('a, button, img, span, i'));
            const target = nodes.find((el) => {
                const hay = (
                    (el.id || '') + ' ' + (el.title || '') + ' ' + (el.alt || '') + ' ' +
                    (el.getAttribute('onclick') || '') + ' ' + (el.className || '')
                ).toLowerCase();
                return hay.includes('captcha') && (
                    hay.includes('refresh') || hay.includes('reload') ||
                    hay.includes('actualizar') || hay.includes('nuevo') ||
                    hay.includes('generar')
                );
            });
            if (target) { target.click(); return true; }
            // Fallback: bump cache-buster on captcha <img>
            const imgs = Array.from(document.images).filter((img) =>
                /captcha/i.test(img.src || '') || /captcha/i.test(img.id || '')
            );
            if (imgs[0]) {
                const u = new URL(imgs[0].src, location.href);
                u.searchParams.set('_', String(Date.now()));
                imgs[0].src = u.toString();
                return true;
            }
            return false;
        }"""
    )
    if clicked:
        logger.info("CAPTCHA image refreshed in-place")
    else:
        logger.debug("No CAPTCHA refresh control found")


def captcha_field_present(html: str) -> bool:
    return "captchaDigitado" in html or "formInicioSesion:captchaDigitado" in html
