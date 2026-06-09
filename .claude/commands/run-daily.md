---
description: Trigger the Daily Brief scheduler wrapper now and monitor completion
---

Run the Daily Brief pipeline now. Do not ask for confirmation; the user invoked this command.

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

## Step 1: trigger the run

```bash
python -m dailybrief run-scheduled
```

This writes `logs/daily-<YYYY-MM-DD>.log`, runs `dailybrief daily`, attempts deploy, and opens the latest report.

## Step 2: report status

Show:

- last 30 lines of `logs/daily-<date>.log`
- files in `daily_reports/<date>/`
- whether `logs/llm-calls.jsonl` has recent successful calls

If it failed, identify the phase: fetch, enrichment, trading, digest, render, deploy, or open.
