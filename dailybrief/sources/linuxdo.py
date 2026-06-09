from __future__ import annotations

import feedparser

from dailybrief.models import RawArticle
from dailybrief.utils import parse_dt, strip_html

from .curl_fetch import curl_fetch
from .v2ex import V2EX_OFF_TOPIC_RE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DailyBriefBot/1.0; +https://github.com/leiting-eric/DailyBrief)",
    "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _is_cloudflare(text: str) -> bool:
    head = text[:500].lower()
    return "just a moment" in head or "cf-chl" in head or (head.startswith("<!doctype html") and "cloudflare" in head)


def _fetch_feed(url: str):
    raw = curl_fetch(url, HEADERS)
    if _is_cloudflare(raw):
        raise RuntimeError("cloudflare challenge page")
    return feedparser.parse(raw)


def fetch_linuxdo(source_id: str, limit: int = 25) -> list[RawArticle]:
    try:
        feed = _fetch_feed("https://linux.do/top.rss?period=daily")
    except Exception:
        feed = _fetch_feed("https://linux.do/latest.rss")
    out: list[RawArticle] = []
    for item in feed.entries or []:
        title = (getattr(item, "title", "") or "").strip()
        link = (getattr(item, "link", "") or "").strip()
        if not title or not link or V2EX_OFF_TOPIC_RE.search(title):
            continue
        out.append(
            RawArticle(
                sourceId=source_id,
                title=title,
                url=link,
                excerpt=strip_html(getattr(item, "summary", "") or getattr(item, "description", ""))[:300],
                publishedAt=parse_dt(getattr(item, "published", None) or getattr(item, "updated", None)),
                category="tech",
            )
        )
        if len(out) >= limit:
            break
    return out
