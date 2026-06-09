from datetime import datetime

from dailybrief.models import ArticleInput, SourceDef
from dailybrief.output.render import group_raw, render_html, render_markdown


def test_group_raw_merges_finance_news_and_filters_disabled():
    registry = [
        SourceDef(id="a", name="A", type="rss", url="https://a.test/rss", category="finance", subcategory="news", enabled=True),
        SourceDef(id="b", name="B", type="rss", url="https://b.test/rss", category="finance", subcategory="news", enabled=False),
    ]
    articles = [
        ArticleInput(sourceId="a", source="A", title="One", url="https://a.test/1", category="finance", publishedAt=datetime(2026, 1, 2)),
        ArticleInput(sourceId="b", source="B", title="Two", url="https://b.test/1", category="finance", publishedAt=datetime(2026, 1, 3)),
    ]
    raw = group_raw(articles, registry)
    assert raw["finance"][0]["sources"][0]["sourceId"] == "_merged"
    assert [a["title"] for a in raw["finance"][0]["sources"][0]["items"]] == ["One"]


def test_render_html_and_markdown_smoke():
    report = {
        "hero_headline": "A compact headline",
        "daily_overview": "Overview text",
        "tech_briefs": [{"title": "Tech", "url": "https://x.test", "source": "X", "summary": "Summary", "importance": 8}],
        "finance_briefs": [],
        "politics_briefs": [],
        "editor_note": "Note",
        "keywords": ["AI"],
    }
    raw = {"tech": [], "finance": [], "politics": []}
    html = render_html(report, raw, "2026-01-02")
    assert "<!doctype html>" in html
    assert "A compact headline" in html
    md = render_markdown(report, "2026-01-02")
    assert "# " in md and "Tech" in md
