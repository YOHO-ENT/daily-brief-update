import json
from pathlib import Path

from scripts.publish_reports import main


def _write_artifacts(root: Path, date: str) -> None:
    day = root / date
    day.mkdir(parents=True)
    (day / f"{date}.html").write_text("<html>report</html>", encoding="utf-8")
    (day / f"{date}.json").write_text('{"hero_headline":"Hero"}', encoding="utf-8")
    (day / f"{date}-articles.json").write_text('{"articles":[]}', encoding="utf-8")
    (root / "index.html").write_text("<html>latest</html>", encoding="utf-8")
    (root / "archive.html").write_text("<html>archive</html>", encoding="utf-8")


def test_publish_reports_copies_static_site_and_writes_health(tmp_path):
    source = tmp_path / "daily_reports"
    target = tmp_path / "public"
    _write_artifacts(source, "2026-06-10")

    assert main(["--source", str(source), "--target", str(target), "--public-url", "http://example.test/brief/"]) == 0

    assert (target / "index.html").exists()
    assert (target / "archive.html").exists()
    assert (target / "2026-06-10" / "2026-06-10.html").exists()
    health = json.loads((target / "health.json").read_text(encoding="utf-8"))
    assert health["status"] == "ok"
    assert health["latest_report_date"] == "2026-06-10"
    assert health["latest_report_url"] == "http://example.test/brief/2026-06-10/2026-06-10.html"
