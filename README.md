# Daily Brief

Daily Brief is a local-first Python pipeline that fetches RSS/API/scraped news sources, enriches them with a pluggable LLM backend, adds market commentary, and writes a self-contained HTML report.

There is no database, no web server, and no web framework. Reports are static files under `daily_reports/<YYYY-MM-DD>/`.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env.local
dailybrief sources check
dailybrief run --dry-run
DAILYBRIEF_LIVE_ALLOWED=true dailybrief run --live --confirm-live --build-site
dailybrief open
```

For one-shot execution without installing the console script:

```bash
python -m dailybrief run --dry-run
```

## Configuration

Local secrets live in `.env.local`, which is gitignored.

Common DeepSeek setup:

```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_key_here
REPORT_LOCALE=zh
REPORT_TZ=Australia/Sydney
```

Supported backends:

- `claude-cli`
- `anthropic`
- `openai`
- `deepseek`
- `minimax`
- `zhipu`

Provider-specific API keys and base URLs are documented in `.env.example`. `LLM_MODEL`, `LLM_API_KEY`, and `LLM_BASE_URL` remain supported.

## Commands

| Task | Command |
|---|---|
| Production-safe pipeline | `dailybrief run --dry-run` / `dailybrief run --live --confirm-live --build-site` |
| Legacy full pipeline | `dailybrief daily` |
| Fetch-only sanity check | `dailybrief dry-run` |
| Notification summary | `dailybrief notify [date] --dry-run` |
| Re-render cached report | `dailybrief render [date]` |
| Re-run market section | `dailybrief regen-trading [date]` |
| Top up missing summaries | `dailybrief regen-enrich <cat:sub> [date]` |
| List sources | `dailybrief sources` |
| Validate source config | `dailybrief sources check` |
| Build GitHub Pages output | `dailybrief build-site` |
| Open latest report | `dailybrief open [date]` |
| LLM usage summary | `dailybrief quota-report` |
| Optional server deploy | `dailybrief deploy [date]` |

`[date]` defaults to today's date in `REPORT_TZ`.

`dailybrief run --dry-run` is plan-only: it does not fetch sources, call an LLM,
write artifacts, deploy, or send notifications. A real run requires both
`--live --confirm-live` and `DAILYBRIEF_LIVE_ALLOWED=true`.

## Outputs

Each full run writes:

```text
daily_reports/<date>/<date>.json
daily_reports/<date>/<date>-articles.json
daily_reports/<date>/<date>.html
logs/llm-calls.jsonl
```

If `OUTPUT_MARKDOWN=true`, the run also writes `<date>.md`.

## Local Scheduler

Install an OS-level daily job:

```bash
dailybrief install --at 08:00 --global
```

This writes `~/.daily-brief-config`, registers the scheduler, and optionally installs the Claude skill/commands into `~/.claude/`.

Manual scheduler-style run:

```bash
dailybrief run-scheduled
```

`run-scheduled` uses the same live gate as production. Set
`DAILYBRIEF_LIVE_ALLOWED=true` in `.env.local` or the service environment before
using it.

Uninstall scheduler and user-level Claude links:

```bash
dailybrief uninstall
```

Project files, reports, and logs are not removed by uninstall.

## GitHub Actions

The workflow in `.github/workflows/daily.yml` runs Python 3.11, installs the package with `pip install -e ".[test]"`, generates the daily report through `dailybrief run --live --confirm-live --build-site`, and publishes `daily_reports/` to `gh-pages`.

Set repository secrets and variables:

- Secrets: one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `ZHIPU_API_KEY`, or generic `LLM_API_KEY`
- Variables: `LLM_BACKEND`, `LLM_MODEL`, `REPORT_LOCALE`, `REPORT_TZ`, `REPORT_HOUR`, `REPORT_DAYS`

## Production Checks

Read-only acceptance and VPS checks live under `scripts/`:

```bash
python3 scripts/check_dailybrief_acceptance.py --days 5 --output-json
python3 scripts/check_vps_production.py --output-json
```

Vultr systemd templates and the deployment runbook are in `deploy/vultr/`.

## Project Layout

```text
dailybrief/
  ai/        # LLM dispatcher, prompts, enrichment, JSON repair
  integrations/notifications/
  storage/   # generated artifact readers/writers
  sources/   # source registry and fetchers
  trading/   # Yahoo chart data, indicators, signals, crypto context
  output/    # static HTML/Markdown rendering
deploy/vultr/
scripts/
tests/
sources.config.json
pyproject.toml
```

## Adding Sources

1. Edit `sources.config.json`.
2. For RSS sources, no Python code is usually needed.
3. For API/scrape sources, add a fetcher under `dailybrief/sources/` and branch in `dailybrief/sources/dispatch.py`.
4. Run:

```bash
dailybrief sources check
dailybrief dry-run
```

## Development Checks

```bash
python -m compileall dailybrief tests
python -m pytest -q
dailybrief sources check
dailybrief run --dry-run --output-json
```
