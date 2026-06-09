from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from dailybrief.models import RawArticle


def fetch_github_trending(source_id: str, limit: int = 25) -> list[RawArticle]:
    html = httpx.get(
        "https://github.com/trending?since=daily",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=20,
        follow_redirects=True,
    ).text
    soup = BeautifulSoup(html, "html.parser")
    out: list[RawArticle] = []
    for article in soup.select("article.Box-row")[:limit]:
        a = article.select_one("h2 a")
        repo = (a.get("href", "") if a else "").strip().lstrip("/")
        if not repo:
            continue
        desc = article.select_one("p")
        description = " ".join(desc.get_text(" ").split()) if desc else ""
        f6 = article.select_one(".f6")
        language = ""
        total_stars = ""
        forks = ""
        stars_today = ""
        if f6:
            lang_el = f6.select_one("[itemprop=programmingLanguage]")
            language = lang_el.get_text(strip=True) if lang_el else ""
            for link in f6.select("a"):
                href = link.get("href", "")
                text = " ".join(link.get_text(" ").split())
                if href.endswith("/stargazers"):
                    total_stars = text
                elif href.endswith("/forks"):
                    forks = text
            for span in f6.select("span"):
                text = " ".join(span.get_text(" ").split())
                if "stars today" in text:
                    stars_today = text
                    break
        meta_parts = []
        if language:
            meta_parts.append(language)
        if total_stars:
            meta_parts.append(f"* {total_stars}")
        if forks:
            meta_parts.append(f"forks {forks}")
        if stars_today:
            meta_parts.append(stars_today)
        out.append(
            RawArticle(
                sourceId=source_id,
                title=repo,
                url=f"https://github.com/{repo}",
                excerpt=description[:300],
                meta=" · ".join(meta_parts),
                category="tech",
            )
        )
    return out
