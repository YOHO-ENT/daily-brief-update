#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${DAILYBRIEF_ROOT:-/home/deploy/DailyBrief}"
REPORT_TARGET="${DAILYBRIEF_REPORTS_TARGET:-/opt/research-stack/runtime/dailybrief-reports}"
REPORT_BASE_URL="${DAILYBRIEF_REPORT_BASE_URL:-http://149.28.156.116/brief/}"

cd "$ROOT"
mkdir -p logs

log_file="logs/dailybrief-service-$(date -u +%F).log"

run_once() {
  printf '[%s] starting DailyBrief production run\n' "$(date -Is)"
  .venv/bin/python -m dailybrief run --live --confirm-live --build-site --output-json
  .venv/bin/python scripts/publish_reports.py \
    --source "$ROOT/daily_reports" \
    --target "$REPORT_TARGET" \
    --public-url "$REPORT_BASE_URL"
  printf '[%s] DailyBrief production run complete\n' "$(date -Is)"
}

run_once 2>&1 | tee -a "$log_file"
