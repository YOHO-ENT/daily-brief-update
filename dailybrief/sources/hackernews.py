from __future__ import annotations

from datetime import datetime

import httpx

from dailybrief.models import RawArticle
from dailybrief.utils import strip_html

HN_BASE = "https://hacker-news.firebaseio.com/v0"


def fetch_hacker_news(source_id: str, limit: int = 30) -> list[RawArticle]:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        ids = client.get(f"{HN_BASE}/topstories.json").json()
        out: list[RawArticle] = []
        for story_id in ids[:limit]:
            try:
                item = client.get(f"{HN_BASE}/item/{story_id}.json").json()
            except Exception:
                continue
            if not item or not item.get("title"):
                continue
            out.append(
                RawArticle(
                    sourceId=source_id,
                    title=item.get("title", ""),
                    url=item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}",
                    excerpt=(
                        strip_html(item.get("text", ""))[:300]
                        if item.get("text")
                        else f"{item.get('score', 0)} points · {item.get('descendants', 0)} comments"
                    ),
                    publishedAt=datetime.fromtimestamp(item["time"]) if item.get("time") else None,
                    category="tech",
                )
            )
        return out
