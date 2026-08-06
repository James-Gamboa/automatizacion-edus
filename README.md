# EDUS Citas Automation (CCSS Costa Rica)

Automates login, CAPTCHA, and appointment booking on **EDUS Citas Web** (`https://edus.ccss.sa.cr/eduscitasweb/`).

### Based on the official guide — with extra automation

This project **follows** the official EDUS automation guide and then goes further: ready-to-run **Python scripts**, a full `edus/` package, and agent **skills** so Hermes / OpenClaw (or similar) can book with natural language instead of rebuilding Playwright from the guide alone.

| Repo | What you get | Link |
|------|----------------|------|
| **This repo (recommended to run)** | Python CLI, `edus/` package, install scripts, agent skills, Hermes/Telegram prompts | [James-Gamboa/automatizacion-edus](https://github.com/James-Gamboa/automatizacion-edus) |
| **Original guide** | Official phases, DOM notes, architecture (build your own agent from the markdown) | [jeudytuanisapps/automatizacion-citas-edus-ccss](https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss) |
| Official guide file | [EDUS-Citas-Automation-Guide.md](https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss/blob/main/EDUS-Citas-Automation-Guide.md) | also copied here as [`EDUS-Citas-Automation-Guide.md`](EDUS-Citas-Automation-Guide.md) |

**What we added on top of the guide**

- Python package `edus/` — login, CAPTCHA OCR voting, booking (Servicio → Especialidad), familiar, watchdog
- CLI `scripts/edus_cli.py` — `book`, `check`, `monitor`, `last`, `validate`
- Install scripts for Windows / macOS / Linux (`scripts/install.ps1`, `scripts/install.sh`)
- Agent skills `edus-citas` + `edus-citas-automation-guide` (so the agent runs the CLI, not invents new browsers)
- Example Telegram prompt: [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md) · Hermes notes: [`HERMES.md`](HERMES.md)
- Hardened config via `.env`, dry-run, WAF-aware retries, schedule helpers

---

## Clone

### Option A — This repo (ready to install and run)

```bash
git clone https://github.com/James-Gamboa/automatizacion-edus.git
cd automatizacion-edus
```

Then jump to [Just install and run](#just-install-and-run).

### Option B — Original guide only

Use this if you want the upstream markdown / skill guide and will implement automation yourself:

```bash
git clone https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss.git
cd automatizacion-citas-edus-ccss
```

### Optional — keep the original guide next to this project

From inside a clone of **this** repo:

```bash
git clone https://github.com/jeudytuanisapps/automatizacion-citas-edus-ccss.git vendor/automatizacion-citas-edus-ccss
```

(`vendor/` is gitignored.)

---

## Just install and run

If you only want to install dependencies and run the automation, use the section for your OS. Then put your cédula and password in `.env` (`EDUS_CEDULA`, `EDUS_CLAVE`). Never commit `.env`.

### macOS

```bash
cd /path/to/automatizacion-edus
chmod +x scripts/install.sh
./scripts/install.sh
# Edit .env → EDUS_CEDULA and EDUS_CLAVE
brew install tesseract tesseract-lang   # if install.sh warned about OCR
python3 scripts/edus_cli.py book --specialty medicina_general --force --dry-run
```

Real booking (after dry-run looks good):

```bash
python3 scripts/edus_cli.py book --specialty medicina_general --force
# or: python3 scripts/edus_cli.py book --specialty odontologia --force
```

### Windows (PowerShell)

```powershell
cd C:\path\to\automatizacion-edus
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Edit .env → EDUS_CEDULA and EDUS_CLAVE
# Install Tesseract if needed: winget install --id UB-Mannheim.TesseractOCR -e
python scripts\edus_cli.py book --specialty medicina_general --force --dry-run
```

Real booking:

```powershell
python scripts\edus_cli.py book --specialty medicina_general --force
```

Prefer the project venv if you created one:

```powershell
.\.venv\Scripts\python.exe scripts\edus_cli.py book --specialty medicina_general --force --dry-run
```

### Linux

```bash
cd /path/to/automatizacion-edus
chmod +x scripts/install.sh
./scripts/install.sh
# Edit .env → EDUS_CEDULA and EDUS_CLAVE
# Tip: sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
python3 scripts/edus_cli.py book --specialty medicina_general --force --dry-run
```

---

## What the guide covers (and what this repo does)

| Guide phase | What it means | In this repo |
|-------------|----------------|--------------|
| Phase 1 — Reconocimiento | Public health-center listing without login | `edus/centros.py` |
| Phase 2 — Login + CAPTCHA | HTTP CAPTCHA download + OCR retries | `edus/login.py`, `edus/captcha.py` |
| Phase 3 — Reserva | Servicio → Especialidad → cupos → confirmar | `edus/booking.py` |
| Phase 4 — Familiar | Book for a family member under the titular | `edus/familiar.py` |
| Phase 5 — Watchdog | Silent monitor when no slots / outside window | `edus/watchdog.py`, schedule scripts |

Typical EDUS flow this CLI follows:

1. Login (cédula + clave + CAPTCHA OCR)
2. Agregar una cita
3. **Servicio** first: `MEDICINA` or `ODONTOLOGIA`
4. **Especialidad**: `MEDICINA GENERAL` or `ODONTOLOGIA GENERAL`
5. Read cupos → reserve → confirm (unless `--dry-run`)

Slots usually release **5:00–8:00 America/Costa_Rica**. Outside that window, `no_slots` is normal. Use `--force` to try anyway.

---

## CLI reference

| Command | Purpose |
|---------|---------|
| `python scripts/edus_cli.py validate` | Check deps / env readiness |
| `python scripts/edus_cli.py book -s medicina_general --force` | Book medicina general |
| `python scripts/edus_cli.py book -s odontologia --force` | Book odontología |
| `python scripts/edus_cli.py check -s medicina_general --force` | Availability only (no reserve) |
| `python scripts/edus_cli.py monitor` | Watchdog (silent if no slots) |
| `python scripts/edus_cli.py last` | Last run result |
| `python scripts/edus_cli.py install-browsers` | Install Chromium |

Flags: `--force` (ignore 5–8am monitor gate), `--dry-run`, `--headed`.

---

## Business rules

1. Credentials only from `EDUS_CEDULA` / `EDUS_CLAVE` (env or `.env`).
2. Monitor window (when slots usually release): **5:00–8:00 America/Costa_Rica**.
3. Auto-book only appointment times in `EDUS_SLOT_START`–`EDUS_SLOT_END` (default 05:00–08:00).
4. Skip dates already present in the appointments table (anti-duplicate).
5. Optional family member via `FAMILIAR_CEDULA` / `FAMILIAR_NOMBRE`.
6. If EDUS returns **Request Rejected** (WAF), stop and wait 15–60 minutes — do not retry in a tight loop.

---

## Schedule (watchdog)

See [`MONITOR.md`](MONITOR.md) for the **alert → you say OK → book** flow.

**Windows Task Scheduler (check-only by default):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_task_scheduler.ps1 -Specialty medicina_general
```

When cupos appear you get a Windows toast + slot list. Then book yourself or tell Telegram `ok, reservame el primero`.

**macOS / Linux (cron):**

```bash
chmod +x scripts/install.sh edus_citas_schedule.sh
./scripts/install.sh
# Example: every 5 minutes during the morning window
# */5 5-7 * * * /path/to/edus_citas_schedule.sh medicina_general
```

---

## Agent / Telegram (optional)

You can drive this CLI from **Hermes** or **OpenClaw** over Telegram (or similar).

1. Clone **this** repo (Option A above) and install.
2. Copy the example prompt from [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md) into your bot (replace `<PROJECT_ROOT>`).
3. Optional deeper setup: [`HERMES.md`](HERMES.md).

The agent should only run `scripts/edus_cli.py` with the project Python — not invent new Playwright scripts.

Skills in this repo (for agents that load local skills):

| Skill | Path |
|-------|------|
| Executable booking | `.agents/skills/edus-citas/` |
| Official guide mirror | `.agents/skills/edus-citas-automation-guide/` |

### Suggested videos (Hermes / OpenClaw)

Community tutorials — not affiliated with this repo. Useful if you want the agent + Telegram gateway first, then point it at this project.

**Hermes**

| Video | Link |
|-------|------|
| Hermes Agent beginner guide (Telegram, skills, scheduling) | [youtube.com/watch?v=CwPUOVUdApE](https://www.youtube.com/watch?v=CwPUOVUdApE) |
| Hermes 24/7 + full Telegram bot setup (also compares OpenClaw) | [youtube.com/watch?v=gzq_4hZsU4E](https://www.youtube.com/watch?v=gzq_4hZsU4E) |
| Build your first Hermes agent (VPS / Docker) | [youtube.com/watch?v=6dkv_mzxPY0](https://www.youtube.com/watch?v=6dkv_mzxPY0) |

**OpenClaw**

| Video | Link |
|-------|------|
| Full OpenClaw setup (VPS, Telegram, skills) | [youtube.com/watch?v=fcZMmP5dsl4](https://www.youtube.com/watch?v=fcZMmP5dsl4) |
| Complete OpenClaw walkthrough | [youtube.com/watch?v=UrPuSAFd_Ss](https://www.youtube.com/watch?v=UrPuSAFd_Ss) |
| freeCodeCamp: OpenClaw full tutorial for beginners | [youtube.com/watch?v=n1sfrc-RjyM](https://www.youtube.com/watch?v=n1sfrc-RjyM) |

After the agent is online, paste [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md) and ask it to run `scripts/edus_cli.py` from this repo.

---

## Project layout

```
edus/                  # Python package (login, captcha, booking, watchdog)
scripts/edus_cli.py    # CLI entrypoint
scripts/install.sh     # macOS / Linux install
scripts/install.ps1    # Windows install
TELEGRAM_PROMPT.md     # example bot prompt (use <PROJECT_ROOT>)
HERMES.md              # Hermes / agent setup
EDUS-Citas-Automation-Guide.md
data/last_result.json  # last run summary
logs/edus.log          # rotating log
.env.example
```

---

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest tests/test_core.py -q
python -m pytest tests/test_smoke_network.py -q
```

Live booking needs valid credentials and available cupos; use `--dry-run` first.

## Security

- Never commit `.env`
- Never put cédula/password in source files
- Prefer `--dry-run` until you trust the flow
