"""Configuration loaded from environment / .env — never hardcode credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from edus.constants import (
    ALIAS_TO_PRESET,
    DEFAULT_MONITOR_END_HOUR,
    DEFAULT_MONITOR_START_HOUR,
    DEFAULT_SLOT_END,
    DEFAULT_SLOT_START,
    EDUS_BASE_URL,
    SPECIALTY_PRESETS,
    SpecialtyPreset,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
LAST_RESULT_PATH = DATA_DIR / "last_result.json"


def _load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        # Minimal fallback parser
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


@dataclass
class Settings:
    cedula: str
    clave: str
    tip_identificacion: str = "0"
    base_url: str = EDUS_BASE_URL
    familiar_cedula: str = ""
    familiar_nombre: str = ""
    excluir_fechas: list[str] = field(default_factory=list)
    centro_salud: str = ""
    headless: bool = True
    slow_mo_ms: int = 0
    captcha_max_attempts: int = 30
    ajax_wait_seconds: float = 4.0
    navigation_timeout_ms: int = 60000
    action_timeout_ms: int = 30000
    monitor_start_hour: int = DEFAULT_MONITOR_START_HOUR
    monitor_end_hour: int = DEFAULT_MONITOR_END_HOUR
    slot_start: str = DEFAULT_SLOT_START
    slot_end: str = DEFAULT_SLOT_END
    enforce_monitor_window: bool = True
    enforce_slot_window: bool = True
    dry_run: bool = False
    tesseract_cmd: str = ""
    log_level: str = "INFO"
    browser_channel: str = ""  # e.g. chrome

    def resolve_preset(self, specialty: str) -> SpecialtyPreset:
        key = ALIAS_TO_PRESET.get(specialty.strip().lower(), specialty.strip().lower())
        if key not in SPECIALTY_PRESETS:
            valid = ", ".join(SPECIALTY_PRESETS)
            raise ValueError(f"Unknown specialty '{specialty}'. Valid: {valid}")
        preset = dict(SPECIALTY_PRESETS[key])
        # Allow env overrides for odontology codes when discovered
        if key == "odontologia":
            svc = os.getenv("ODONTO_SERVICIO", "").strip()
            esp = os.getenv("ODONTO_ESPECIALIDAD", "").strip()
            if svc:
                preset["servicio_code"] = svc
            if esp:
                preset["especialidad_code"] = esp
        if key == "medicina_general":
            svc = os.getenv("SERVICIO", "").strip()
            esp = os.getenv("ESPECIALIDAD", "").strip()
            if svc:
                preset["servicio_code"] = svc
            if esp:
                preset["especialidad_code"] = esp
        return preset  # type: ignore[return-value]


def load_settings(*, require_credentials: bool = True) -> Settings:
    _load_dotenv()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    cedula = os.getenv("EDUS_CEDULA", "").strip()
    clave = os.getenv("EDUS_CLAVE", "").strip()
    if require_credentials:
        if not cedula:
            raise RuntimeError(
                "EDUS_CEDULA is not set. Add it to .env or export it in the environment."
            )
        if not clave:
            raise RuntimeError(
                "EDUS_CLAVE is not set. Add it to .env or export it in the environment."
            )

    excluir_raw = os.getenv("EXCLUIR_FECHAS", "").strip()
    excluir = [p.strip() for p in excluir_raw.split(",") if p.strip()] if excluir_raw else []

    return Settings(
        cedula=cedula,
        clave=clave,
        tip_identificacion=os.getenv("EDUS_TIP_IDENTIFICACION", "0").strip() or "0",
        base_url=os.getenv("EDUS_BASE_URL", EDUS_BASE_URL).strip() or EDUS_BASE_URL,
        familiar_cedula=os.getenv("FAMILIAR_CEDULA", "").strip(),
        familiar_nombre=os.getenv("FAMILIAR_NOMBRE", "").strip(),
        excluir_fechas=excluir,
        centro_salud=os.getenv("CENTRO_SALUD", "").strip(),
        headless=_env_bool("EDUS_HEADLESS", True),
        slow_mo_ms=_env_int("EDUS_SLOW_MO_MS", 0),
        captcha_max_attempts=_env_int("EDUS_CAPTCHA_MAX_ATTEMPTS", 15),
        ajax_wait_seconds=_env_float("EDUS_AJAX_WAIT_SECONDS", 4.0),
        navigation_timeout_ms=_env_int("EDUS_NAVIGATION_TIMEOUT_MS", 60000),
        action_timeout_ms=_env_int("EDUS_ACTION_TIMEOUT_MS", 30000),
        monitor_start_hour=_env_int("EDUS_MONITOR_START_HOUR", DEFAULT_MONITOR_START_HOUR),
        monitor_end_hour=_env_int("EDUS_MONITOR_END_HOUR", DEFAULT_MONITOR_END_HOUR),
        slot_start=os.getenv("EDUS_SLOT_START", DEFAULT_SLOT_START).strip() or DEFAULT_SLOT_START,
        slot_end=os.getenv("EDUS_SLOT_END", DEFAULT_SLOT_END).strip() or DEFAULT_SLOT_END,
        enforce_monitor_window=_env_bool("EDUS_ENFORCE_MONITOR_WINDOW", True),
        enforce_slot_window=_env_bool("EDUS_ENFORCE_SLOT_WINDOW", True),
        dry_run=_env_bool("EDUS_DRY_RUN", False),
        tesseract_cmd=os.getenv("TESSERACT_CMD", "").strip(),
        log_level=os.getenv("EDUS_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        browser_channel=os.getenv("EDUS_BROWSER_CHANNEL", "").strip(),
    )


def get_optional_settings() -> Optional[Settings]:
    try:
        return load_settings(require_credentials=False)
    except Exception:
        return None
