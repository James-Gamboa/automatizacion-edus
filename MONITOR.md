# Hermes + Telegram auto-alert for EDUS cupos

Your idea: **Hermes Agent + Telegram** watches EDUS and messages you when there are cupos. You reply OK and pick the slot.

## Flow

```
every 5 min (Hermes cron, no LLM)
    → edus_monitor_alert.py
    → project .venv + monitor --check-only
    → no cupos / outside 5–8 CR  → empty stdout → silent
    → hay cupos                 → Telegram message with list
You on Telegram:
    → "ok, reservame el primero"
    → or "ok, escogeme el de las 07:00"
Hermes agent:
    → runs book CLI (must invoke terminal tool for real)
```

## Already set up on this PC (if you ran setup)

| Item | Value |
|------|--------|
| Script | `%USERPROFILE%\.hermes\scripts\edus_monitor_alert.py` |
| Job | `edus-cupos` |
| Schedule | `*/5 5-7 * * *` (only **05:00–07:59**, not all day) |
| Mode | `--no-agent` (no model cost) |
| Deliver | `telegram` |
| Window | Python still only looks for cupos **5:00–8:00 America/Costa_Rica** |

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
hermes cron create "*/5 5-7 * * *" --no-agent --script edus_monitor_alert.py --deliver telegram --name "edus-cupos"
```

4. Gateway must be running (`hermes cron status` → Gateway is running).

5. Paste [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md) into the bot so when you say OK it runs `book`, not JSON.

### How to know your bot will alert you

| Check | What to do |
|-------|------------|
| Job active + Deliver telegram | `hermes cron list` |
| Gateway running | `hermes cron status` |
| Script exists | `dir $env:LOCALAPPDATA\hermes\scripts\edus_monitor_alert.py` |
| Force one run | `hermes cron run <job_id>` then `hermes cron runs <job_id>` → should say `completed` |
| Telegram | Message only if there is stdout (cupos **or** error). **No cupos = silence** (normal). |

Silent between checks does **not** mean it is broken.

## What you send on Telegram

When the bot alerts with cupos:

```text
ok, reservame el primero
```

```text
ok, escogeme el de las 07:00
```

Optional specialty:

```text
ok, medicina general, el primero
```

## Pause / resume

```powershell
hermes cron pause <job_id>
hermes cron resume <job_id>
hermes cron remove <job_id>
```

Or in Telegram chat: “pausa el monitoreo de citas EDUS”.

## Difference vs Windows Task Scheduler

| | Hermes cron → Telegram | Task Scheduler |
|--|------------------------|----------------|
| Alert channel | Telegram | Windows toast |
| Needs Hermes gateway | Yes | No |
| LLM cost for check | No (`--no-agent`) | No |
| Confirm booking | Reply on Telegram | Run CLI / tell bot |
| PowerShell windows | No | Yes (annoying) — **prefer Hermes only** |

**Recommendation:** use Hermes cron only. Do **not** also register `setup_task_scheduler.ps1` unless you want a local toast backup (it can flash PowerShell every few minutes).

If a leftover Windows task is opening PowerShell:

```powershell
Unregister-ScheduledTask -TaskName "EDUS-Citas-Monitor" -Confirm:$false
```

See also: [`HERMES.md`](HERMES.md), [`TELEGRAM_PROMPT.md`](TELEGRAM_PROMPT.md).
