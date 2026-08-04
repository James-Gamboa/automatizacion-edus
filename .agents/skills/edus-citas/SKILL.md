---
name: edus-citas
description: >-
  Automates EDUS CCSS (Costa Rica) medical appointment booking with Playwright,
  CAPTCHA OCR, and silent watchdog monitoring. Use when the user asks to book
  EDUS appointments, citas EDUS, medicina general, odontología, check EDUS
  availability, start monitoring, or review the last booking result.
---

# EDUS Citas Automation Skill

Fully automated booking for **EDUS Citas Web** (`https://edus.ccss.sa.cr/eduscitasweb/`) following the official guide.

## When to use

Apply this skill immediately when the user says things like:

- "Use el skill de citas EDUS y sáqueme una cita de medicina general."
- "Use el skill de citas EDUS y sáqueme una cita de odontología."
- "Revise si hay citas disponibles."
- "¿Cuál fue el resultado de la última ejecución?"
- "Inicie el monitoreo automático."

Do **not** ask the user for step-by-step clicks. Run the CLI. Credentials come only from env / `.env` (`EDUS_CEDULA`, `EDUS_CLAVE`).

## Prerequisites (once)

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
# Prefer project venv after first setup:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Ensure `.env` exists (copied from `.env.example`) with:

- `EDUS_CEDULA`
- `EDUS_CLAVE`

Optional: `FAMILIAR_CEDULA`, `FAMILIAR_NOMBRE`, `CENTRO_SALUD`, `EXCLUIR_FECHAS`, slot/monitor windows.

Validate:

```powershell
.\.venv\Scripts\python.exe scripts\edus_cli.py validate
```

## Command map (natural language → CLI)

Always `cd` to the **project root** first.

**ALWAYS use the project venv Python** (avoids Hermes/system Pillow `_imaging` errors):

```text
.\.venv\Scripts\python.exe
```

Prefer `--force` for interactive user requests so the monitor window does not block them; the slot-time window still applies.

| User intent | Command |
|-------------|---------|
| Book medicina general | `.\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force` |
| Book odontología | `.\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty odontologia --force` |
| Check availability only | `.\.venv\Scripts\python.exe scripts\edus_cli.py check --specialty medicina_general --force` |
| Last result | `.\.venv\Scripts\python.exe scripts\edus_cli.py last` |
| Start monitoring (Task Scheduler) | `powershell -ExecutionPolicy Bypass -File scripts/setup_task_scheduler.ps1` |
| One-shot watchdog | `.\.venv\Scripts\python.exe scripts\edus_cli.py monitor --specialty medicina_general` |
| Safe dry-run | `.\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force --dry-run --headed` |

Show the browser while debugging: add `--headed`.

## Agent workflow

```
Task Progress:
- [ ] 1. Read this skill + HERMES.md
- [ ] 2. Validate with PROJECT venv python
- [ ] 3. Confirm .env has EDUS_CEDULA + EDUS_CLAVE (never print the password)
- [ ] 4. Run the mapped CLI command with the venv python
- [ ] 5. Summarize data/last_result.json for the user (EN + ES)
```

### Booking rules (must enforce via config/CLI)

1. Open Playwright → login with CAPTCHA OCR retries → navigate citas.
2. If `FAMILIAR_*` set, switch to family member before adding cita.
3. Select service/specialty (medicina general codes `1` / `1033`; odontología by label).
4. Parse cupos; exclude `EXCLUIR_FECHAS`.
5. **Only reserve** slots whose time is inside `EDUS_SLOT_START`–`EDUS_SLOT_END` (default 05:00–08:00). Out-of-window slots: notify, do not book.
6. Skip dates that already have an appointment (anti-duplicate).
7. Confirm reservation unless `--dry-run`.
8. Save result to `data/last_result.json` and write logs under `logs/edus.log`.
9. Always close the browser (CLI context manager).

### Monitor / cron semantics

`monitor` / `edus_citas_schedule.sh` follow the guide:

- No cupos → silent exit 0
- Actionable result → print summary exit 0
- Error → print to stderr exit 1

Default monitor window: **5:00–8:00 America/Costa_Rica**.

## Output to the user

Respond in **English and Spanish**. Include:

- Status (`booked`, `no_slots`, `slots_out_of_window`, `error`, …)
- Specialty, date/time if booked
- Out-of-window slots that were only notified
- Path to logs if failed

Never echo `EDUS_CLAVE` or full `.env` contents.

## Troubleshooting

### `Request Rejected` / CAPTCHA non-image / `cannot identify image file`

EDUS sits behind a WAF. Rapid login/CAPTCHA retries can temporarily ban your IP.

1. **Stop retrying** for 15–30 minutes.
2. In `.env` set `EDUS_CAPTCHA_MAX_ATTEMPTS=10` (or lower).
3. Retry headed once with the project venv python.
4. The skill **stops immediately** on WAF rejection instead of hammering retries.

### CAPTCHA OCR failures

Valid PNG CAPTCHAs are required. Install Tesseract (`winget install UB-Mannheim.TesseractOCR`).

### Extra reference

- Official guide: [EDUS-Citas-Automation-Guide.md](../../../EDUS-Citas-Automation-Guide.md)
- DOM IDs: [reference.md](reference.md)
- Hermes setup: [HERMES.md](../../../HERMES.md)
