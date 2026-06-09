from __future__ import annotations

import httpx

from dailybrief.models import RawArticle
from dailybrief.utils import compact_number, parse_dt

BASE = "https://reply-vc-90459984647.us-central1.run.app/v1/articles/leaderboard"


def _is_english(entry: dict) -> bool:
    langs = entry.get("langsDetected")
    if langs:
        return "en" in langs
    return entry.get("lang") in ("en", "zxx")


def _meta(entry: dict) -> str:
    author = entry.get("author") or {}
    parts = [f"@{author.get('handle', '')}"]
    if isinstance(author.get("followers"), (int, float)):
        parts.append(f"{compact_number(author['followers'])} 粉丝")
    if isinstance(entry.get("viewCount"), (int, float)):
        parts.append(f"{compact_number(entry['viewCount'])} 阅")
    if isinstance(entry.get("likeCount"), (int, float)):
        parts.append(f"{compact_number(entry['likeCount'])} 赞")
    if isinstance(entry.get("retweetCount"), (int, float)) and entry["retweetCount"] > 0:
        parts.append(f"{compact_number(entry['retweetCount'])} 转")
    return " · ".join([p for p in parts if p and p != "@"])


def fetch_attention_vc(source_id: str, limit: int = 20) -> list[RawArticle]:
    url = f"{BASE}?window=3d&category=ai&lang=en&limit=30"
    r = httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; DailyBriefBot/1.0)", "Accept": "application/json"},
        timeout=15,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"attentionvc HTTP {r.status_code}")
    entries = [e for e in (r.json().get("entries") or []) if _is_english(e)]
    out = []
    for e in entries[:limit]:
        author = e.get("author") or {}
        handle = author.get("handle", "")
        out.append(
            RawArticle(
                sourceId=source_id,
                title=e.get("title", ""),
                url=f"https://x.com/{handle}/status/{e.get('tweetId')}",
                excerpt=" ".join((e.get("previewText") or "").split())[:300],
                publishedAt=parse_dt(e.get("tweetCreatedAt")),
                category="tech",
                meta=_meta(e),
            )
        )
    return out
