---
name: daily-brief
description: Operational knowledge for the Python Daily Brief digest pipeline. Load when running, debugging, scheduling, adding sources, switching LLM backends, regenerating report sections, checking quota, or diagnosing rendered output.
---

# daily-brief Python Skill

Daily Brief is a Python-only local-first pipeline. It fetches news sources, enriches selected groups with an LLM, computes market signals, and renders static HTML to `daily_reports/<date>/`.

## Project root

All paths are relative to the directory containing `sources.config.json` and `pyproject.toml`.

If outside the project, read `~/.daily-brief-config`:

```bash
python - <<'PY'
from pathlib import Path
cfg = Path.home() / ".daily-brief-config"
if cfg.exists():
    print(cfg.read_text().strip())
else:
    raise SystemExit("daily-brief not installed")
PY
```

## Commands

| Need | Command |
|---|---|
| Full pipeline | `dailybrief daily` |
| Fetch only | `dailybrief dry-run` |
| Re-render cached report | `dailybrief render [date]` |
| Re-run trading | `dailybrief regen-trading [date]` |
| Top up summaries | `dailybrief regen-enrich <cat:sub> [date]` |
| Build static site | `dailybrief build-site` |
| Open report | `dailybrief open [date]` |
| LLM usage | `dailybrief quota-report` |
| Install scheduler | `dailybrief install --at 08:00 --global` |
| Scheduled wrapper | `dailybrief run-scheduled` |
| Uninstall scheduler | `dailybrief uninstall` |

Use `python -m dailybrief ...` when the console script is unavailable.

## Invariants

- Source registry is only `sources.config.json`.
- LLM calls go through `dailybrief.ai.llm.run_llm()`.
- Date labels use `today_key()` and `REPORT_TZ`.
- UI strings must support both `REPORT_LOCALE=zh` and `REPORT_LOCALE=en`.
- Single source failures must not abort the whole report.
- Output files are `<date>.json`, `<date>-articles.json`, and `<date>.html`.

## Debugging

1. Scheduled/full-run log: `logs/daily-<date>.log`
2. LLM log: `logs/llm-calls.jsonl`
3. Source sanity: `dailybrief dry-run`
4. Render-only check: `dailybrief render [date]`
5. Trading-only check: `dailybrief regen-trading [date]`

If the report exists but layout looks wrong, re-render before rerunning LLM.

## Adding sources

Edit `sources.config.json`; for non-RSS sources add a fetcher in `dailybrief/sources/` and wire it in `dailybrief/sources/dispatch.py`. Validate with `dailybrief sources check`, then run `dailybrief dry-run`.
