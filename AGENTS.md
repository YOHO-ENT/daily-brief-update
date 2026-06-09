# AGENTS.md

Operational knowledge for AI coding agents working on this repo.

## Subagent Usage

- At the start of every task, explicitly consider whether subagents would materially help.
- Use subagents only when active tool rules permit delegation and the task splits cleanly into useful independent work.
- Keep the main thread responsible for the critical path, integration, final verification, and user-facing summary.

## What This Project Is

`daily-brief` is a Python-only, local-first pipeline that fetches RSS/API/scraped news sources, runs LLM enrichment, adds market commentary, and renders a single self-contained HTML report.

No web framework, no DB, no server. It can run locally through the OS scheduler or in GitHub Actions publishing to GitHub Pages.

## Project Layout

```text
dailybrief/
  ai/        # LLM dispatcher, prompts, enrichment, JSON repair
  sources/   # registry loader + per-source fetchers
  trading/   # Yahoo finance, indicators, signals, watchlist
  output/    # HTML/Markdown renderer with inlined CSS/JS
tests/
sources.config.json
pyproject.toml
bootstrap.py
```

## Core Invariants

1. `sources.config.json` is the only source registry. Do not hardcode source lists in Python.
2. LLM calls go through `dailybrief.ai.llm.run_llm()`.
3. Date keys use `dailybrief.utils.today_key()` and honor `REPORT_TZ`.
4. Localization uses `REPORT_LOCALE=zh|en`; UI strings must exist in both languages.
5. Per-source fetch errors are non-fatal.
6. The output contract is `daily_reports/<date>/<date>.json`, `<date>-articles.json`, and `<date>.html`.
7. Do not reintroduce Node/npm or a web framework.

## Commands

| Task | Command |
|---|---|
| Full pipeline | `dailybrief daily` |
| Fetch sanity check | `dailybrief dry-run` |
| Re-render cached report | `dailybrief render [date]` |
| Re-run market section | `dailybrief regen-trading [date]` |
| Top up missing summaries | `dailybrief regen-enrich <cat:sub> [date]` |
| Static-site generator | `dailybrief build-site` |
| List sources | `dailybrief sources` |
| Validate sources | `dailybrief sources check` |
| Open report | `dailybrief open [date]` |
| LLM usage | `dailybrief quota-report` |
| Install scheduler | `dailybrief install --at 08:00 --global` |
| Scheduled wrapper | `dailybrief run-scheduled` |
| Uninstall scheduler | `dailybrief uninstall` |

Use `python -m dailybrief ...` if the console script is not installed.

## Adding a Source

1. Edit `sources.config.json`.
2. For non-RSS types, add a fetcher under `dailybrief/sources/` and branch in `dailybrief/sources/dispatch.py`.
3. Run `dailybrief sources check`.
4. Run `dailybrief dry-run`.

## Debugging

1. `logs/daily-<YYYY-MM-DD>.log` for scheduled/full pipeline output.
2. `logs/llm-calls.jsonl` for LLM calls, latency, success, and error category.
3. `dailybrief quota-report` for backend usage summary.
4. `dailybrief render [date]` for display-only fixes without LLM cost.

## What Not To Do

- Do not add Next.js, Express, Flask, FastAPI, or any server requirement.
- Do not import provider SDKs directly from pipeline/render/source code.
- Do not hardcode sources outside `sources.config.json`.
- Do not add npm wrappers for normal operation.
- Do not write report files from ad hoc agent scripts; use the CLI.
