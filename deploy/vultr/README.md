# DailyBrief on Vultr

This directory contains a minimal systemd production shell for DailyBrief. It
keeps DailyBrief local-first: no database, no web framework, and no old
US-equity-news payloads.

## Layout

Default paths used by the unit files:

```text
/home/deploy/DailyBrief
/home/deploy/DailyBrief/.venv
/home/deploy/DailyBrief/daily_reports
/home/deploy/DailyBrief/logs
/etc/dailybrief/dailybrief.env
/opt/research-stack/runtime/dailybrief-reports
```

Install the project and dependencies as the `deploy` user:

```bash
cd /home/deploy/DailyBrief
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python -m dailybrief run --dry-run --output-json
```

## Environment

Store secrets only in `/etc/dailybrief/dailybrief.env` or another private env
file referenced by the systemd service. Do not commit it.

Minimum live gate:

```env
DAILYBRIEF_LIVE_ALLOWED=true
REPORT_LOCALE=zh
REPORT_TZ=Asia/Shanghai
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=...
DAILYBRIEF_REPORT_BASE_URL=http://149.28.156.116/brief/
DAILYBRIEF_REPORTS_TARGET=/opt/research-stack/runtime/dailybrief-reports
```

Optional notifications are disabled by default:

```env
SLACK_ENABLED=false
TELEGRAM_ENABLED=false
EMAIL_ENABLED=false
DAILYBRIEF_REPORT_BASE_URL=https://example.com
```

## Install systemd units

```bash
sudo cp deploy/vultr/dailybrief.service /etc/systemd/system/dailybrief.service
sudo cp deploy/vultr/dailybrief.timer /etc/systemd/system/dailybrief.timer
sudo systemctl daemon-reload
sudo systemctl enable --now dailybrief.timer
```

The timer runs daily at 08:00 Asia/Shanghai without changing the VPS system
timezone.

## Operations

Manual production run:

```bash
sudo systemctl start dailybrief.service
```

Inspect status and logs:

```bash
systemctl list-timers dailybrief.timer
systemctl status dailybrief.service --no-pager
journalctl -u dailybrief.service -n 200 --no-pager
tail -n 200 /home/deploy/DailyBrief/logs/dailybrief-service-$(date -u +%F).log
```

Read-only checks:

```bash
/home/deploy/DailyBrief/.venv/bin/python scripts/check_vps_production.py --output-json
/home/deploy/DailyBrief/.venv/bin/python scripts/check_dailybrief_acceptance.py --days 5 --output-json
curl -fsS http://127.0.0.1:8080/brief/health.json
```

Live notification delivery is never automatic unless you explicitly add
`--send --confirm-send` to the service command and enable the target channel env
vars.
