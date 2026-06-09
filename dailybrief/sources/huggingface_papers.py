from __future__ import annotations

import json

from dailybrief.models import RawArticle
from dailybrief.utils import parse_dt

from .curl_fetch import curl_fetch


def fetch_huggingface_papers(
    source_id: str,
    keywords: list[str] | None = None,
    limit: int = 30,
) -> list[RawArticle]:
    raw = curl_fetch(
        "https://huggingface.co/api/daily_papers",
        {"User-Agent": "DailyBriefBot/1.0", "Accept": "application/json"},
    )
    papers = json.loads(raw)
    keyword_list = [k.lower() for k in (keywords or [])]

    def keep(item: dict) -> bool:
        if not keyword_list:
            return True
        paper = item.get("paper") or {}
        haystack = " ".join(
            [
                paper.get("title") or "",
                paper.get("summary") or "",
                *[str(x) for x in (paper.get("ai_keywords") or [])],
            ]
        ).lower()
        return any(k in haystack for k in keyword_list)

    kept = [p for p in papers if keep(p)]
    kept.sort(key=lambda x: (x.get("paper") or {}).get("upvotes") or 0, reverse=True)
    out: list[RawArticle] = []
    for item in kept[:limit]:
        paper = item.get("paper") or {}
        out.append(
            RawArticle(
                sourceId=source_id,
                title=paper.get("title", ""),
                url=f"https://huggingface.co/papers/{paper.get('id')}",
                excerpt=(paper.get("summary") or "")[:300],
                publishedAt=parse_dt(paper.get("publishedAt")),
                meta=f"thumbs {paper.get('upvotes', 0)}",
                category="tech",
            )
        )
    return out
