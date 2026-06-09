from datetime import datetime, timezone

from dailybrief import utils


def test_today_key_accepts_common_china_timezone_alias(monkeypatch):
    monkeypatch.setenv("REPORT_TZ", "China/Shanghai")
    assert utils.today_key(datetime(2026, 6, 8, 18, 0, tzinfo=timezone.utc)) == "2026-06-09"
