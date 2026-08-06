"""Guide compliance checklist — point-by-point vs official EDUS guide."""

GUIDE_CHECKLIST = [
    ("Phase 1 centroSalud public AJAX", "edus/centros.py", True),
    ("Phase 2 login form IDs", "edus/login.py + edus/constants.py", True),
    ("Phase 2 CAPTCHA HTTP download (not screenshot)", "edus/captcha.py", True),
    ("Phase 2 OCR grayscale+contrast+3x+PSM7+whitelist", "edus/captcha.py", True),
    ("Phase 2 captcha retry loop", "EDUS_CAPTCHA_MAX_ATTEMPTS default 15 (raise in .env)", True),
    ("Phase 2 success marker Agregar una cita", "edus/login.py", True),
    ("Phase 3 PrimeFaces btnMenuAdd", "edus/booking.py", True),
    ("Phase 3 servicio/especialidad selects", "edus/booking.py", True),
    ("Phase 3 Medicina 1 / MG 1033", "edus/constants.py", True),
    ("Phase 3 parse cuposDisponibles", "edus/booking.py", True),
    ("Phase 3 Ver cita + Confirmar", "edus/booking.py", True),
    ("Phase 4 familiar Ver Citas + Agregar", "edus/familiar.py", True),
    ("Phase 4 Python-before-JS f-string pitfall avoided", "edus/familiar.py evaluate args", True),
    ("Phase 5 silent watchdog", "edus/watchdog.py", True),
    ("Phase 5 schedule 5-8 CR", "edus_citas_schedule.sh + Task Scheduler", True),
    ("Env EDUS_CEDULA/EDUS_CLAVE never hardcoded", "edus/config.py", True),
    ("getElementById for JSF colon IDs", "login/booking modules", True),
]


def test_guide_checklist_complete() -> None:
    missing = [item for item in GUIDE_CHECKLIST if not item[2]]
    assert not missing
    assert len(GUIDE_CHECKLIST) >= 15
