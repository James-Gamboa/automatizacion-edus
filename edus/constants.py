"""Constants and specialty presets aligned with the official EDUS guide."""

from __future__ import annotations

from typing import TypedDict


EDUS_BASE_URL = "https://edus.ccss.sa.cr/eduscitasweb/"
EDUS_CONTEXT_PATH = "/CitasWebPF"
CAPTCHA_PATH = f"{EDUS_CONTEXT_PATH}/captcha"
LOGIN_SUCCESS_MARKER = "Agregar una cita"

# DOM IDs from the official guide
FORM_LOGIN = "formInicioSesion"
LOGIN_USER = "formInicioSesion:usuario"
LOGIN_PASS = "formInicioSesion:clave"
LOGIN_CAPTCHA = "formInicioSesion:captchaDigitado"
LOGIN_SUBMIT = "formInicioSesion:ejecutarPaso1"
LOGIN_ID_TYPE = "formInicioSesion:tipIdentificacion_input"

FORM_MAIN = "formSIAC"
BTN_ADD_CITA = "formSIAC:btnMenuAdd"
MENU_SERVICIOS = "formSIAC:menuServicios_input"
MENU_ESPECIALIDADES = "formSIAC:menuEspecialidades_input"
TABLA_CUPOS = "formSIAC:cuposDisponibles"
TABLA_CITAS = "formSIAC:tablaCitas"
TABLA_FAMILIARES = "formSIAC:tablaFamiliares"
TABLA_CITAS_FAM = "formSIAC:tablaCitasFam"

# Identification types
ID_TYPE_NATIONAL = "0"
ID_TYPE_TEMPORARY = "6"
ID_TYPE_FOREIGN = "7"

# Default codes from the official guide
DEFAULT_SERVICIO_MEDICINA = "1"
DEFAULT_ESPECIALIDAD_MEDICINA_GENERAL = "1033"

# Costa Rica timezone for release/monitor window
TZ_COSTA_RICA = "America/Costa_Rica"
DEFAULT_MONITOR_START_HOUR = 5
DEFAULT_MONITOR_END_HOUR = 8

# Appointment-slot booking window (business rule)
DEFAULT_SLOT_START = "05:00"
DEFAULT_SLOT_END = "08:00"

COMMON_ERRORS = {
    "No se encontraron cupos disponibles": "no_slots",
    "El paciente posea citas para ese mismo día": "duplicate_same_day",
    "El servicio o la especialidad no estén disponibles para el género": "gender_restriction",
    "La cita haya sido asignada a otro usuario": "slot_taken",
    "gestionó todas las citas disponibles": "slots_exhausted",
}


class SpecialtyPreset(TypedDict):
    key: str
    label: str
    servicio_code: str
    especialidad_code: str
    servicio_labels: list[str]
    especialidad_labels: list[str]


SPECIALTY_PRESETS: dict[str, SpecialtyPreset] = {
    "medicina_general": {
        "key": "medicina_general",
        "label": "Medicina General",
        "servicio_code": DEFAULT_SERVICIO_MEDICINA,
        "especialidad_code": DEFAULT_ESPECIALIDAD_MEDICINA_GENERAL,
        "servicio_labels": ["MEDICINA"],
        "especialidad_labels": ["MEDICINA GENERAL"],
    },
    "odontologia": {
        "key": "odontologia",
        "label": "Odontología",
        "servicio_code": "",  # resolve by label when empty
        "especialidad_code": "",
        "servicio_labels": ["ODONTO"],
        "especialidad_labels": [
            "ODONTOLOGIA GENERAL",
            "ODONTOLOGÍA GENERAL",
            "ODONTOLOGIA",
            "ODONTOLOGÍA",
        ],
    },
}


ALIAS_TO_PRESET: dict[str, str] = {
    "medicina": "medicina_general",
    "medicina general": "medicina_general",
    "medicina_general": "medicina_general",
    "general": "medicina_general",
    "mg": "medicina_general",
    "odontologia": "odontologia",
    "odontología": "odontologia",
    "odonto": "odontologia",
    "dental": "odontologia",
}
