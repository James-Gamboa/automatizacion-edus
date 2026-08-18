"""Send EDUS cupos alerts to Telegram with tappable reserve buttons."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def reservation_command(fecha: str, hora: str) -> str:
    return f"reserva esta {fecha} {hora}"


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _candidate_env_files() -> list[Path]:
    files: list[Path] = []
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        files.append(Path(local) / "hermes" / ".env")
    files.append(Path.home() / ".hermes" / ".env")
    files.append(Path(__file__).resolve().parent.parent / ".env")
    return files


def telegram_credentials() -> tuple[str, str]:
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    for path in _candidate_env_files():
        for key, value in _parse_env_file(path).items():
            env.setdefault(key, value)
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    allowed = env.get("TELEGRAM_ALLOWED_USERS", "").split(",")[0].strip()
    chat_id = (
        env.get("TELEGRAM_HOME_CHANNEL", "").strip()
        or env.get("TELEGRAM_CHAT_ID", "").strip()
        or allowed
    )
    return token, chat_id


def reply_keyboard(slots: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for slot in slots[:8]:
        fecha = str(slot.get("fecha") or "?").strip()
        hora = str(slot.get("hora") or "?").strip()
        label = reservation_command(fecha, hora)
        if len(label) > 64:
            label = f"{fecha} {hora}"[:64]
        rows.append([{"text": label}])
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": True,
        "is_persistent": False,
    }


def send_telegram_message(
    text: str,
    *,
    reply_markup: Optional[dict[str, Any]] = None,
) -> bool:
    token, chat_id = telegram_credentials()
    if not token or not chat_id or not text.strip():
        return False
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw) if raw else {}
        return bool(parsed.get("ok"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def send_cupos_alert(text: str, slots: list[dict[str, Any]]) -> bool:
    markup = reply_keyboard(slots) if slots else None
    if markup and not markup.get("keyboard"):
        markup = None
    return send_telegram_message(text, reply_markup=markup)
