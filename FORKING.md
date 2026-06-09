# Forking Daily Brief

This project is now Python-only. The pipeline has no database, server, or frontend framework; it writes static reports to `daily_reports/`.

## Common Customizations

### Change LLM backend

Edit `.env.local`:

```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_key_here
REPORT_LOCALE=zh
REPORT_TZ=Australia/Sydney
```

All LLM calls go through `dailybrief.ai.llm.run_llm()`. Do not call provider SDKs directly from business logic.

### Add or disable a source

Edit `sources.config.json`; this remains the single source of truth.

Fields:

- `id`
- `name`
- `type`: `rss`, `api`, or `scrape`
- `url`
- `category`: `tech`, `finance`, or `politics`
- optional `subcategory`, `enabled`, `useCurl`, `lang`, `locales`, `notes`

Validate and smoke-test:

```bash
dailybrief sources check
dailybrief dry-run
```

For non-RSS sources, add a fetcher under `dailybrief/sources/` and branch in `dailybrief/sources/dispatch.py`.

### Change UI copy or layout

HTML is rendered by `dailybrief/output/render.py`. UI strings live in the `TEXTS_ZH` and `TEXTS_EN` dictionaries. After editing layout or copy, re-render cached data:

```bash
dailybrief render [date]
```

### Change market watchlist

Edit `dailybrief/trading/watchlist.py`, then run:

```bash
dailybrief regen-trading [date]
dailybrief render [date]
```

### Schedule locally

```bash
dailybrief install --at 08:00 --global
dailybrief run-scheduled
dailybrief uninstall
```

`run-scheduled` logs to `logs/daily-<date>.log`, runs the full pipeline, tries deploy, and opens the report on success.

### Publish with GitHub Pages

Use `.github/workflows/daily.yml`. It installs Python 3.11 dependencies, runs `python -m dailybrief daily`, builds the static site, and publishes `daily_reports/` to `gh-pages`.

## Debugging

- Full scheduled logs: `logs/daily-<date>.log`
- LLM call history: `logs/llm-calls.jsonl`
- Usage summary: `dailybrief quota-report`
- Fetch-only check: `dailybrief dry-run`
- Display-only fix: `dailybrief render [date]`

## Invariants

- Do not hardcode source lists in Python; use `sources.config.json`.
- Do not bypass `run_llm()`.
- Do not hardcode report dates or timezones; use `today_key()`.
- Per-source fetch failures are non-fatal.
- Keep output shape compatible: `<date>.json`, `<date>-articles.json`, `<date>.html`.
