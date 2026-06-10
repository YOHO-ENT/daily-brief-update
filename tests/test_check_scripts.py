import json
from pathlib import Path

from scripts.check_dailybrief_acceptance import check_dailybrief_acceptance
from scripts import check_vps_production as vps


def _write_report(root: Path, date: str, *, secret: str = "") -> None:
    day = root / date
    day.mkdir(parents=True)
    report = {
        "hero_headline": "Hero",
        "daily_overview": "Overview",
        "tech_briefs": [{"title": "One", "url": "https://x.test", "source": "X", "summary": "S", "importance": 8}],
        "finance_briefs": [],
        "politics_briefs": [],
        "editor_note": "",
        "keywords": [],
    }
    articles = {
        "date": date,
        "articles": [{"sourceId": "x", "title": "One", "url": "https://x.test", "category": "tech", "source": "X"}],
    }
    (day / f"{date}.json").write_text(json.dumps(report), encoding="utf-8")
    (day / f"{date}-articles.json").write_text(json.dumps(articles), encoding="utf-8")
    (day / f"{date}.html").write_text(f"<html>Hero {secret}</html>", encoding="utf-8")


def test_acceptance_passes_complete_artifact(tmp_path):
    _write_report(tmp_path, "2026-01-02")

    payload = check_dailybrief_acceptance(output_dir=tmp_path, required_days=1)

    assert payload["status"] == "passed"
    assert payload["daily_checks"][0]["article_count"] == 1


def test_acceptance_fails_on_secret_pattern(tmp_path):
    _write_report(tmp_path, "2026-01-02", secret="https://hooks.slack.com/services/T/B/C")

    payload = check_dailybrief_acceptance(output_dir=tmp_path, required_days=1)

    assert payload["status"] == "failed"
    assert "secret_pattern_detected" in payload["daily_checks"][0]["warnings"]


def test_vps_check_with_mocked_systemd(tmp_path, monkeypatch):
    _write_report(tmp_path, "2026-01-02")
    monkeypatch.setenv("DAILYBRIEF_LIVE_ALLOWED", "true")
    monkeypatch.setattr(vps.shutil, "which", lambda name: "/bin/systemctl" if name == "systemctl" else None)

    def fake_run_cmd(cmd):
        if cmd[:3] == ["git", "rev-parse", "--short"]:
            return {"returncode": 0, "stdout": "abc123\n", "stderr": ""}
        if cmd[:2] == ["git", "status"]:
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if cmd[:2] == ["systemctl", "is-active"]:
            return {"returncode": 0, "stdout": "active\n", "stderr": ""}
        if cmd[:2] == ["systemctl", "is-enabled"]:
            return {"returncode": 0, "stdout": "enabled\n", "stderr": ""}
        if cmd and cmd[0] == "journalctl":
            return {"returncode": 0, "stdout": "ok\n", "stderr": ""}
        return {"returncode": 1, "stdout": "", "stderr": "unexpected"}

    monkeypatch.setattr(vps, "_run_cmd", fake_run_cmd)

    payload = vps.check_vps_production(
        output_dir=tmp_path,
        service="dailybrief.service",
        timer="dailybrief.timer",
        env_file=tmp_path / "missing.env",
    )

    assert payload["status"] == "ready"
    assert payload["git"]["revision"] == "abc123"

