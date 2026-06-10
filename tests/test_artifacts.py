import json
from datetime import datetime

from dailybrief.models import ArticleInput
from dailybrief.storage.artifacts import load_articles, load_report, paths_for_date, write_report_outputs


def test_artifact_round_trip(tmp_path):
    date = "2026-01-02"
    report = {
        "hero_headline": "A compact headline",
        "daily_overview": "Overview",
        "tech_briefs": [{"title": "Tech", "url": "https://x.test", "source": "X", "summary": "Summary", "importance": 9}],
        "finance_briefs": [],
        "politics_briefs": [],
        "editor_note": "",
        "keywords": [],
    }
    articles = [
        ArticleInput(
            sourceId="github-trending",
            title="Repo",
            url="https://x.test/repo",
            category="tech",
            source="GitHub",
            publishedAt=datetime(2026, 1, 2, 8, 0),
        )
    ]

    paths = write_report_outputs(date, report, articles, tmp_path)

    assert paths.html.exists()
    assert load_report(date, tmp_path)["hero_headline"] == "A compact headline"
    assert load_articles(date, tmp_path)[0].title == "Repo"
    assert json.loads(paths.articles_json.read_text(encoding="utf-8"))["date"] == date
    assert paths_for_date(date, tmp_path).report_json == paths.report_json

