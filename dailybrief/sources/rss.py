from __future__ import annotations

import feedparser
import httpx

from dailybrief.models import Category, RawArticle
from dailybrief.utils import parse_dt, strip_html

from .curl_fetch import curl_fetch

PARSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DailyBriefBot/1.0; +https://github.com/)",
}

CURL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_rss(
    source_id: str,
    url: str,
    category: Category,
    *,
    limit: int = 30,
    use_curl: bool | None = None,
) -> list[RawArticle]:
    if use_curl:
        raw = curl_fetch(url, CURL_HEADERS)
    else:
        with httpx.Client(timeout=15, headers=PARSER_HEADERS, follow_redirects=True) as client:
            raw = client.get(url).text

    feed = feedparser.parse(raw)
    out: list[RawArticle] = []
    for item in (feed.entries or [])[:limit]:
        title = (getattr(item, "title", "") or "").strip()
        link = (getattr(item, "link", "") or "").strip()
        if not title or not link:
            continue
        content = (
            getattr(item, "summary", None)
            or getattr(item, "description", None)
            or getattr(item, "content", [{}])[0].get("value", "")
            if getattr(item, "content", None)
            else ""
        )
        out.append(
            RawArticle(
                sourceId=source_id,
                title=title,
                url=link,
                excerpt=strip_html(str(content))[:300],
                publishedAt=parse_dt(getattr(item, "published", None) or getattr(item, "updated", None)),
                category=category,
            )
        )
    return out
