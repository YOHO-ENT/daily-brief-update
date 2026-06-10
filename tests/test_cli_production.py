import pytest

from dailybrief import cli


def test_run_dry_run_does_not_fetch(monkeypatch, capsys):
    def fail_fetch():
        raise AssertionError("fetch_all should not run during production dry-run")

    monkeypatch.setattr(cli, "fetch_all", fail_fetch)

    cli.main(["run", "--dry-run", "--output-json"])

    captured = capsys.readouterr()
    assert '"mode": "dry-run"' in captured.out
    assert '"will_fetch_sources": false' in captured.out


def test_run_live_requires_confirm(monkeypatch, capsys):
    monkeypatch.setenv("DAILYBRIEF_LIVE_ALLOWED", "true")

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["run", "--live"])

    assert excinfo.value.code == 2
    assert "--confirm-live" in capsys.readouterr().err


def test_run_live_requires_env_gate(monkeypatch, capsys):
    monkeypatch.delenv("DAILYBRIEF_LIVE_ALLOWED", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["run", "--live", "--confirm-live"])

    assert excinfo.value.code == 2
    assert "DAILYBRIEF_LIVE_ALLOWED=true" in capsys.readouterr().err


def test_notify_live_requires_confirm_before_loading_artifacts(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["notify", "2026-01-02", "--live"])

    assert excinfo.value.code == 2
    assert "--confirm-send" in capsys.readouterr().err


def test_notify_dry_run_uses_artifact_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        "dailybrief.integrations.notifications.summary.load_report",
        lambda date: {
            "hero_headline": "Hero",
            "daily_overview": "Overview",
            "tech_briefs": [{"title": "One", "source": "X", "summary": "S", "importance": 7}],
            "finance_briefs": [],
            "politics_briefs": [],
        },
    )
    monkeypatch.setattr("dailybrief.integrations.notifications.summary.report_url", lambda date, base_url=None: "https://example.test/report.html")

    cli.main(["notify", "2026-01-02", "--dry-run", "--channels", "slack", "--output-json"])

    captured = capsys.readouterr()
    assert '"channel": "slack"' in captured.out
    assert '"status": "dry_run"' in captured.out

