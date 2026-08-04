"""CAPTCHA download + OCR following the official EDUS guide."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from edus.config import LOG_DIR
from edus.constants import CAPTCHA_PATH

logger = logging.getLogger("edus.captcha")

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
GIF_MAGIC = b"GIF8"
WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


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


def _clean_ocr_text(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (raw or "").strip())


def _add_white_border(img: Image.Image, px: int = 12) -> Image.Image:
    return ImageOps.expand(img, border=px, fill=255)


def preprocess_captcha(image_path: Path, output_path: Path, *, variant: str = "guide") -> Path:
    """Guide baseline + extra variants tuned for EDUS 270×70 CAPTCHAs."""
    img = Image.open(image_path).convert("L")

    if variant == "guide":
        img = ImageEnhance.Contrast(img).enhance(2.0)
        scale = 3
    elif variant == "guide4x":
        img = ImageEnhance.Contrast(img).enhance(2.2)
        scale = 4
    elif variant == "autocontrast":
        img = ImageOps.autocontrast(img, cutoff=2)
        img = ImageEnhance.Contrast(img).enhance(2.5)
        scale = 3
    elif variant == "threshold_120":
        img = ImageOps.autocontrast(img)
        img = img.point(lambda p: 255 if p > 120 else 0)
        scale = 3
    elif variant == "threshold_150":
        img = ImageOps.autocontrast(img)
        img = img.point(lambda p: 255 if p > 150 else 0)
        scale = 3
    elif variant == "sharp":
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        scale = 3
    elif variant == "median":
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = ImageEnhance.Contrast(img).enhance(2.0)
        scale = 3
    elif variant == "invert":
        img = ImageOps.autocontrast(img)
        img = ImageOps.invert(img)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        scale = 3
    else:
        img = ImageEnhance.Contrast(img).enhance(2.0)
        scale = 3

    width, height = img.size
    img = img.resize((width * scale, height * scale), Image.LANCZOS)
    img = _add_white_border(img, 16)
    img.save(output_path)
    return output_path


def _run_tesseract(tess: str, image_path: Path, *, psm: str) -> str:
    result = subprocess.run(
        [
            tess,
            str(image_path),
            "-",
            "--oem",
            "3",
            "--psm",
            psm,
            "-c",
            f"tessedit_char_whitelist={WHITELIST}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return _clean_ocr_text(result.stdout or "")


def _score_candidate(text: str) -> int:
    """Higher is better. EDUS CAPTCHAs are typically 5–7 alphanumerics."""
    n = len(text)
    if n < 4 or n > 8:
        return 0
    score = 10
    if n == 6:
        score += 5
    elif n in (5, 7):
        score += 3
    # Prefer mixed or letters+digits (real EDUS captchas often mix both)
    has_alpha = any(c.isalpha() for c in text)
    has_digit = any(c.isdigit() for c in text)
    if has_alpha and has_digit:
        score += 2
    return score


def ocr_captcha(image_path: Path, *, tesseract_cmd: str = "") -> str:
    """
    Multi-variant OCR with voting. Returns best consensus string (or "").
    Guide baseline (~30-40%): grayscale + contrast + 3x + PSM7.
    """
    tess = resolve_tesseract_cmd(tesseract_cmd)
    if not tess:
        raise RuntimeError(
            "tesseract not found. Install Tesseract OCR and optionally set TESSERACT_CMD."
        )
    if not is_image_bytes(image_path.read_bytes()):
        raise CaptchaDownloadError(f"Not a valid image file: {image_path}")

    variants = (
        "guide",
        "guide4x",
        "autocontrast",
        "threshold_120",
        "threshold_150",
        "sharp",
        "median",
        "invert",
    )
    psms = ("7", "8", "13", "6")
    votes: Counter[str] = Counter()
    scored: list[tuple[int, str]] = []

    with tempfile.TemporaryDirectory(prefix="edus_captcha_") as tmp:
        tmp_path = Path(tmp)
        for variant in variants:
            processed = tmp_path / f"captcha_{variant}.png"
            preprocess_captcha(image_path, processed, variant=variant)
            for psm in psms:
                cleaned = _run_tesseract(tess, processed, psm=psm)
                if not cleaned:
                    continue
                score = _score_candidate(cleaned)
                logger.debug("OCR variant=%s psm=%s => %r score=%s", variant, psm, cleaned, score)
                if score <= 0:
                    continue
                votes[cleaned] += 1
                scored.append((score + votes[cleaned], cleaned))

    if not scored:
        logger.warning("OCR produced no usable candidates for %s", image_path)
        _save_debug_captcha(image_path, tag="empty")
        return ""

    # Prefer majority vote among good lengths; break ties with score
    majority = votes.most_common()
    best_vote_count = majority[0][1]
    tied = [t for t, c in majority if c == best_vote_count]
    if len(tied) == 1 and best_vote_count >= 2:
        chosen = tied[0]
    else:
        # Highest combined score among tied (or all)
        pool = tied if tied else [t for _, t in scored]
        chosen = max(pool, key=lambda t: (_score_candidate(t), votes[t], len(t)))

    logger.info(
        "OCR chosen=%r votes=%s (top=%s)",
        chosen,
        votes[chosen],
        majority[:3],
    )
    return chosen


def _save_debug_captcha(image_path: Path, *, tag: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        dest = LOG_DIR / f"captcha_debug_{tag}_{int(time.time())}.png"
        dest.write_bytes(image_path.read_bytes())
        logger.debug("Saved debug CAPTCHA to %s", dest)
    except Exception:
        pass


async def _collect_captcha_urls(page) -> list[str]:
    """Prefer the official /CitasWebPF/captcha endpoint; never use logos/SVGs."""
    urls: list[str] = []
    try:
        origin = await page.evaluate("() => location.origin") or "https://edus.ccss.sa.cr"
    except Exception:
        origin = "https://edus.ccss.sa.cr"

    stamp = int(time.time() * 1000)
    urls.append(f"{origin}{CAPTCHA_PATH}?{stamp}")
    urls.append(f"{origin}/CitasWebPF/captcha?{stamp}")
    urls.append("https://edus.ccss.sa.cr/CitasWebPF/captcha?" + str(stamp))

    try:
        discovered = await page.evaluate(
            """() => {
                const out = [];
                for (const img of document.images) {
                    const src = img.currentSrc || img.src || '';
                    if (!src) continue;
                    const hay = (src + ' ' + (img.id || '') + ' ' + (img.alt || '')).toLowerCase();
                    if (hay.includes('logo') || hay.includes('.svg') || hay.includes('barcelona-layout')) {
                        continue;
                    }
                    if (hay.includes('/captcha') || hay.includes('captcha')) {
                        out.push(src.split(';')[0]);
                    }
                }
                return [...new Set(out)];
            }"""
        )
        for src in discovered or []:
            if src and src not in urls:
                urls.append(src)
    except Exception as exc:
        logger.debug("Could not discover captcha URLs from DOM: %s", exc)

    return urls


async def download_captcha(page, dest: Path) -> Path:
    """Download CAPTCHA via HTTP with session cookies (not screenshot)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    candidates = await _collect_captcha_urls(page)
    last_error = "no candidates"

    for url in candidates:
        low = url.lower()
        if ".svg" in low or "logo" in low or "barcelona-layout" in low:
            continue
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
        if "svg" in ctype or "html" in ctype or not is_image_bytes(body):
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
    """Best-effort in-page refresh; full page reload is preferred for a new CAPTCHA."""
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
            return false;
        }"""
    )
    if clicked:
        logger.info("CAPTCHA image refreshed in-place")


def captcha_field_present(html: str) -> bool:
    return "captchaDigitado" in html or "formInicioSesion:captchaDigitado" in html
