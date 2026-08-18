# Hermes / Telegram — EDUS Citas

Executable skill for Hermes (install locally):

```text
~/.hermes/skills/edus-citas/SKILL.md
```

It tells the agent to run this repo's CLI (not invent Playwright from scratch).

---

## One-time setup

1. Copy `.env.example` → `.env` and set `EDUS_CEDULA` / `EDUS_CLAVE`.
2. Install deps (pick your OS):

**macOS / Linux**

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Or: python -m venv .venv && .\.venv\Scripts\python.exe -m pip install -r requirements.txt
#     .\.venv\Scripts\python.exe -m playwright install chromium
```

3. Validate:

```bash
# macOS / Linux
python3 scripts/edus_cli.py validate

# Windows (prefer project venv if you have one)
.\.venv\Scripts\python.exe scripts\edus_cli.py validate
```

4. Install skill into Hermes (from the project root):

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.hermes\skills\edus-citas" | Out-Null
Copy-Item -Force .agents\skills\edus-citas\* "$env:USERPROFILE\.hermes\skills\edus-citas\"
```

```bash
# macOS / Linux
mkdir -p ~/.hermes/skills/edus-citas
cp -R .agents/skills/edus-citas/* ~/.hermes/skills/edus-citas/
```

5. Restart Hermes and confirm skill `edus-citas` appears.

---

## CRITICAL: which Python to use

Always use the **project venv** (or the Python that ran `install.sh` / `install.ps1`), **not** Hermes' own Python (avoids Pillow `_imaging` conflicts).

```text
Windows:  <PROJECT_ROOT>\.venv\Scripts\python.exe
macOS/Linux: <PROJECT_ROOT>/.venv/bin/python
```

Example:

```bash
cd <PROJECT_ROOT>
# Windows
.\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force --dry-run

# macOS / Linux
./.venv/bin/python scripts/edus_cli.py book --specialty medicina_general --force --dry-run
```

---

## Generic Telegram / Hermes prompt (copy-paste)

Prefer the standalone example file: [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md).

Replace `<PROJECT_ROOT>` with your local clone path  
(example Windows: `C:\Users\YOU\automatizacion-edus` · example macOS: `/Users/YOU/automatizacion-edus`).

```
Eres el bot de Telegram para sacar citas EDUS (CCSS Costa Rica).
El proyecto YA está instalado. NO lo configures desde cero. NO ofrezcas instalarlo.

RUTA DEL PROYECTO:
<PROJECT_ROOT>

Python OBLIGATORIO (venv del proyecto — NUNCA el python de Hermes):
Windows: <PROJECT_ROOT>\.venv\Scripts\python.exe
macOS/Linux: <PROJECT_ROOT>/.venv/bin/python

Skills / docs:
- ~/.hermes/skills/edus-citas/SKILL.md
- <PROJECT_ROOT>/HERMES.md
- <PROJECT_ROOT>/TELEGRAM_PROMPT.md
- <PROJECT_ROOT>/scripts/edus_cli.py
- <PROJECT_ROOT>/.env  (EDUS_CEDULA / EDUS_CLAVE; NUNCA imprimas la clave)

Interpreta mensajes:
- "medicina general" / "sáqueme una cita" → medicina_general
- "odontología" / "odonto" → odontologia
- "hay cupos?" → check (sin reservar)
- "último resultado" → last
- Si no dice especialidad, pregunta: ¿Medicina general o Odontología?

Flujo EDUS: Login + CAPTCHA → Agregar cita → Servicio → Especialidad → cupos → reservar.
NO inventes scripts Playwright. Solo ejecuta el CLI.

Comandos (ajusta el python según el OS):
cd <PROJECT_ROOT>
python scripts/edus_cli.py book --specialty medicina_general --force
python scripts/edus_cli.py book --specialty odontologia --force
python scripts/edus_cli.py check --specialty medicina_general --force
python scripts/edus_cli.py last

Reglas:
- Cupos suelen salir 5:00–8:00 America/Costa_Rica
- "No se encontraron cupos" = no_slots (no es fallo de instalación)
- "Request Rejected" → DETENTE, avisa esperar; no reintentar en bucle
- Responde en español, breve: Estado / Especialidad / Detalle
```

---

## Watchdog cron → Telegram (your main idea)

Hermes runs a **script-only** job every 5 minutes. No LLM. If EDUS has cupos (inside 5–8 CR), stdout is **delivered to Telegram**. You reply OK and the chat agent runs `book`.

```powershell
# Script must live here:
#   %USERPROFILE%\.hermes\scripts\edus_monitor_alert.py
# (copy from scripts/hermes_edus_monitor_alert.py and set project path)

hermes cron create "every 5m" --no-agent --script edus_monitor_alert.py --deliver telegram --name "edus-cupos"
hermes cron list
hermes cron status
```

Hermes still ticks `every 5m`. The script searches **every 5 min at 05:00–07:59 CR**, and **at most every 20 min** outside that window (`EDUS_OFF_HOURS_EVERY_MIN`, default 20). No Telegram if EDUS has no cupos. If cupos exist (including hours after 08:00), send the list. Does not auto-book.

Full guide: [`MONITOR.md`](MONITOR.md)

When Telegram says there are cupos:

```text
ok, reservame el primero
```

Optional Windows Task Scheduler (toast only): `scripts/setup_task_scheduler.ps1`

---

## Blocker checklist before live booking

- [ ] `python scripts/edus_cli.py validate` (or project venv) all OK
- [ ] EDUS not returning `Request Rejected` (WAF)
- [ ] Dry-run succeeds with login
- [ ] Then remove `--dry-run` for a real reservation
