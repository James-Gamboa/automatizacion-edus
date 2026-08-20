# Hermes + Telegram: list cupos, do not auto-book

Script-only cron (`--no-agent`). **Never reserves.** Telegram only gets a **list** when EDUS has cupos.

## Flow

```
Hermes cron every 5 min (no LLM)
    05:00–07:59 CR -> search every 5 min
        -> cupos nuevos -> Telegram (una vez por lista; no repite la misma)
        -> sin cupos -> silencio
        -> ya reservaste cita -> monitor pausado (silencio total)
    other hours    -> search + heartbeat cada ~20 min ("monitor activo, sin cupos")
    -> hay cupos (even if hora is after 08:00) -> Telegram list
```

You book later yourself if you want that slot. After a successful **book** (medicina u odontologia), alerts stop automatically.

To search again later:

```powershell
.\.venv\Scripts\python.exe scripts\edus_cli.py monitor --resume
```

To search every 10 minutes outside 5–8 instead of 20, set `EDUS_OFF_HOURS_EVERY_MIN=10` on the Hermes job environment.

## Already set up on this PC (if you ran setup)

| Item     | Value                                                                                 |
| -------- | ------------------------------------------------------------------------------------- |
| Script   | `%LOCALAPPDATA%\hermes\scripts\edus_monitor_alert.py`                                 |
| Job      | `edus-cupos`                                                                          |
| Schedule | `every 5m` tick; **search** every 5 min at 05:00–07:59 CR, every **20 min** otherwise |
| Mode     | `--no-agent` + `--check-only` (list only)                                             |
| Deliver  | `telegram`                                                                            |

Check:

```powershell
hermes cron list
hermes cron status
```

Test one run now (forces the job on next tick / manual):

```powershell
hermes cron run 90dff3c89b88
```

(Use the job id from `hermes cron list`.)

## Install from scratch (any machine)

1. Project installed + `.env` with credentials + `.venv` working.
2. Copy script to the **Hermes scripts folder** (Windows often uses LocalAppData, not `~/.hermes`):

```powershell
$dest = "$env:LOCALAPPDATA\hermes\scripts"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item scripts\hermes_edus_monitor_alert.py "$dest\edus_monitor_alert.py"
# Set EDUS_PROJECT_ROOT or edit ROOT path inside the file
```

3. Create cron:

```powershell
hermes cron create "every 5m" --no-agent --script edus_monitor_alert.py --deliver telegram --name "edus-cupos"
```

4. Gateway must be running (`hermes cron status` → Gateway is running).

5. Cron lists cupos only — it does **not** auto-book.

### How to know your bot will alert you

| Check                         | What to do                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------------ |
| Job active + Deliver telegram | `hermes cron list`                                                                   |
| Gateway running               | `hermes cron status`                                                                 |
| Script exists                 | `dir $env:LOCALAPPDATA\hermes\scripts\edus_monitor_alert.py`                         |
| Force one run                 | `hermes cron run <job_id>` then `hermes cron runs <job_id>` → should say `completed` |
| Telegram                      | Message only if there is a cupos **list** (or error). **No cupos = silence**.        |

Silent between checks does **not** mean it is broken.

## What Telegram looks like

```text
VIBRI
EDUS - hay citas (NO reservadas)
Especialidad: Medicina General

Lista:
  1. 14/08/2026 09:00
  2. 15/08/2026 07:00

Toca el boton de abajo para reservar esa cita.
```

Telegram lock-screen preview starts with **VIBRI**. Under the message Telegram shows a **button per cita**. Tap `reserva esta fecha hora` and the bot books that slot. No message if there are no cupos.

The cron does **not** book. If you want that slot, tap the Telegram button. Hermes skips the LLM and runs `book` immediately.

## Pause / resume

```powershell
hermes cron pause <job_id>
hermes cron resume <job_id>
hermes cron remove <job_id>
```

Or in Telegram chat: “pausa el monitoreo de citas EDUS”.

## Difference vs Windows Task Scheduler

|                      | Hermes cron → Telegram | Task Scheduler                          |
| -------------------- | ---------------------- | --------------------------------------- |
| Alert channel        | Telegram               | Windows toast                           |
| Needs Hermes gateway | Yes                    | No                                      |
| LLM cost for check   | No (`--no-agent`)      | No                                      |
| Confirm booking      | You decide later       | Optional toast                          |
| PowerShell windows   | No                     | Yes (annoying) — **prefer Hermes only** |

**Recommendation:** use Hermes cron only. Do **not** also register `setup_task_scheduler.ps1` unless you want a local toast backup (it can flash PowerShell every few minutes).

If a leftover Windows task is opening PowerShell:

```powershell
Unregister-ScheduledTask -TaskName "EDUS-Citas-Monitor" -Confirm:$false
```

See also: [`HERMES.md`](HERMES.md), [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md).
