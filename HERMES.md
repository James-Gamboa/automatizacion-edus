# Hermes Agent — EDUS Citas

Executable skill for Hermes (install locally):

```text
~/.hermes/skills/edus-citas/SKILL.md
```

It tells Hermes to run this repo's CLI (not invent Playwright from scratch).

## One-time setup

1. Copy `.env.example` → `.env` and set `EDUS_CEDULA` / `EDUS_CLAVE`.
2. Create the project venv and install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Or: `powershell -File scripts/install.ps1`

3. Validate:

```powershell
.\.venv\Scripts\python.exe scripts\edus_cli.py validate
```

4. Install skill into Hermes:

```powershell
# From the project root
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.hermes\skills\edus-citas" | Out-Null
Copy-Item -Force .agents\skills\edus-citas\* "$env:USERPROFILE\.hermes\skills\edus-citas\"
```

5. Restart Hermes and confirm skill `edus-citas` appears.

## CRITICAL: which Python to use

Always use the **project venv**, not Hermes' own Python (avoids Pillow `_imaging` conflicts):

```powershell
cd <PROJECT_ROOT>
.\.venv\Scripts\python.exe scripts\edus_cli.py validate
.\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force --dry-run --headed
```

Wrapper:

```powershell
.\scripts\edus.cmd validate
.\scripts\edus.cmd book --specialty medicina_general --force --dry-run --headed
```

## Prompt for Hermes (copy-paste)

Replace `<PROJECT_ROOT>` with your local path (example: `C:\Users\YOU\automatizacion-edus`).

```
El proyecto YA está instalado. NO lo configures desde cero.

RUTA EXACTA DEL PROYECTO:
<PROJECT_ROOT>

Python OBLIGATORIO (venv del proyecto):
<PROJECT_ROOT>\.venv\Scripts\python.exe

Archivos:
- %USERPROFILE%\.hermes\skills\edus-citas\SKILL.md
- <PROJECT_ROOT>\HERMES.md
- <PROJECT_ROOT>\scripts\edus_cli.py
- <PROJECT_ROOT>\.env  (EDUS_CEDULA / EDUS_CLAVE; NO imprimas la clave)

Ejecuta EXACTAMENTE:
cd /d <PROJECT_ROOT>
<PROJECT_ROOT>\.venv\Scripts\python.exe scripts\edus_cli.py validate
<PROJECT_ROOT>\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force --dry-run --headed

Si dry-run OK:
<PROJECT_ROOT>\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force
<PROJECT_ROOT>\.venv\Scripts\python.exe scripts\edus_cli.py last

Si ves Request Rejected o ImportError de PIL, DETENTE y avísame.
No uses el python del venv de Hermes para este proyecto.
```

## Watchdog cron (guide Phase 5)

```yaml
# Hermes cron idea:
#   script: edus_citas_schedule.sh   # or scripts/run_monitor.ps1 on Windows
#   schedule: every 5m
#   no_agent: true
#   deliver: telegram
```

Windows: `scripts/setup_task_scheduler.ps1`

## Blocker checklist before live booking

- [ ] `.\.venv\Scripts\python.exe scripts\edus_cli.py validate` all OK
- [ ] EDUS not returning `Request Rejected` (WAF)
- [ ] Dry-run succeeds with login
- [ ] Then remove `--dry-run` for a real reservation
