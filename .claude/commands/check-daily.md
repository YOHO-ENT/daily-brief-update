---
description: Check Daily Brief status: scheduler, latest report, logs, and LLM calls
---

Show current Daily Brief state. Gather and report; do not ask questions first.

## Step 0: locate the project root

```bash
python - <<'PY'
from pathlib import Path
cfg = Path.home() / ".daily-brief-config"
if cfg.exists():
    print(cfg.read_text().strip())
elif (Path.cwd() / "sources.config.json").exists():
    print(Path.cwd())
else:
    raise SystemExit("daily-brief not installed. Run: dailybrief install --global")
PY
```

Change into the printed path.

## Step 1: gather state

Run and summarize:

```bash
python -m dailybrief sources check
python -m dailybrief quota-report
find daily_reports -maxdepth 2 -name "*.html" | sort | tail -5
ls -lt logs | head
```

Scheduler checks:

- Windows: `Get-ScheduledTaskInfo -TaskName DailyBrief`
- macOS: `launchctl list | grep com.daily-brief`
- Linux: `crontab -l | grep daily-brief`

## Step 2: synthesize

Report:

- latest report date and size
- scheduler presence/status
- last run log result
- LLM success/failure summary
- anomalies and the next diagnostic command
