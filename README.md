# EDUS Citas Automation (CCSS Costa Rica)

Production-ready Playwright automation + Cursor agent skill to monitor and book appointments on **EDUS Citas Web**, following the [official automation guide](https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss/blob/main/EDUS-Citas-Automation-Guide.md).

A local copy of that guide lives in this repo: [`EDUS-Citas-Automation-Guide.md`](EDUS-Citas-Automation-Guide.md).

Official upstream reference (optional local clone):

```powershell
git clone https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss.git vendor/automatizacion-citas-edus-ccss
```

(`vendor/` is gitignored — clone it locally if you want the upstream copy.)

### Agent skills (in this repo)

| Skill | `.agents/skills` | `.claude/skills` |
|-------|------------------|------------------|
| `edus-citas` (executable booking) | yes | yes |
| `edus-citas-automation-guide` (official guide) | yes | yes |

## What it does

- Logs in with cédula + password + CAPTCHA OCR (Tesseract, retry loop)
- Opens “Agregar una cita” (titular or grupo familiar)
- Selects **Medicina General** or **Odontología**
- Reads available cupos, filters excluded dates and the allowed time window
- Reserves and confirms the first valid slot
- Writes a structured result + rotating logs
- Supports silent watchdog mode for Task Scheduler / cron

## Quick start (Windows)

```powershell
cd C:\Users\jjgue\automatizacion-edus
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
copy .env.example .env   # if install did not create it
# Edit .env → set EDUS_CEDULA and EDUS_CLAVE (never commit .env)
python scripts\edus_cli.py validate
python scripts\edus_cli.py book --specialty medicina_general --force --dry-run
```

Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) for Windows and, if needed, set `TESSERACT_CMD` in `.env`.

## Agent skill usage

The skill lives at `.agents/skills/edus-citas/SKILL.md`. In Cursor, say:

- “Use el skill de citas EDUS y sáqueme una cita de medicina general.”
- “Use el skill de citas EDUS y sáqueme una cita de odontología.”
- “Revise si hay citas disponibles.”
- “¿Cuál fue el resultado de la última ejecución?”
- “Inicie el monitoreo automático.”

The agent runs `scripts/edus_cli.py` — you do not need to click through EDUS manually.

## CLI

| Command | Purpose |
|---------|---------|
| `python scripts/edus_cli.py book -s medicina_general --force` | Book medicina general |
| `python scripts/edus_cli.py book -s odontologia --force` | Book odontología |
| `python scripts/edus_cli.py check -s medicina_general --force` | Availability only |
| `python scripts/edus_cli.py monitor` | Watchdog (silent if no slots) |
| `python scripts/edus_cli.py last` | Last result |
| `python scripts/edus_cli.py validate` | Dependency check |
| `python scripts/edus_cli.py install-browsers` | Install Chromium |

Flags: `--force` (ignore 5–8am monitor gate), `--dry-run`, `--headed`.

## Business rules

1. Credentials only from `EDUS_CEDULA` / `EDUS_CLAVE` (env or `.env`).
2. Monitor window (when slots usually release): **5:00–8:00 America/Costa_Rica**.
3. Auto-book only appointment times in `EDUS_SLOT_START`–`EDUS_SLOT_END` (default 05:00–08:00). Other times are reported, not booked.
4. Skip dates already present in the appointments table (anti-duplicate).
5. Optional family member via `FAMILIAR_CEDULA` / `FAMILIAR_NOMBRE`.

## Windows Task Scheduler

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_task_scheduler.ps1 -Specialty medicina_general
```

Creates a task that runs every 5 minutes; the Python watchdog stays silent outside the Costa Rica release window and when there are no cupos.

## Linux / cron

```bash
chmod +x scripts/install.sh edus_citas_schedule.sh
./scripts/install.sh
# cron: */5 5-7 * * * /path/to/edus_citas_schedule.sh medicina_general
```

## Project layout

```
edus/                  # Python package (login, captcha, booking, watchdog)
scripts/edus_cli.py    # CLI entrypoint
.agents/skills/edus-citas/SKILL.md
data/last_result.json  # last run summary
logs/edus.log          # rotating log
.env.example
```

## Guide compliance map

| Guide phase | Implementation |
|-------------|----------------|
| Phase 2 Login + CAPTCHA HTTP download + OCR PSM7 | `edus/login.py`, `edus/captcha.py` |
| Phase 3 Reserva (PrimeFaces add, servicio, especialidad, cupos, confirmar) | `edus/booking.py` |
| Phase 4 Grupo familiar DOM walk | `edus/familiar.py` |
| Phase 5 Watchdog silent/noisy + schedule | `edus/watchdog.py`, `edus_citas_schedule.sh`, Task Scheduler scripts |
| DOM IDs / pitfalls | `edus/constants.py` + getElementById usage |

## Tests

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_core.py -q
python -m pytest tests/test_smoke_network.py -q
```

Live booking requires valid credentials and available cupos; use `--dry-run` first.

## Security

- Never commit `.env`
- Never put cédula/password in source files
- Prefer `--dry-run` until you trust the flow
