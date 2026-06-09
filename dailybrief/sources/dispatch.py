from __future__ import annotations

from dailybrief.models import RawArticle, SourceDef

from .attentionvc import fetch_attention_vc
from .github_trending import fetch_github_trending
from .hackernews import fetch_hacker_news
from .huggingface_papers import fetch_huggingface_papers
from .linuxdo import fetch_linuxdo
from .rss import fetch_rss
from .v2ex import fetch_v2ex


def fetch_source(source: SourceDef) -> list[RawArticle]:
    if source.id == "hackernews":
        return fetch_hacker_news(source.id)
    if source.id == "github-trending":
        return fetch_github_trending(source.id)
    if source.id == "v2ex-hot":
        return fetch_v2ex(source.id)
    if source.id == "linuxdo":
        return fetch_linuxdo(source.id)
    if source.id == "attentionvc-ai":
        return fetch_attention_vc(source.id)
    if source.id == "huggingface-papers":
        return fetch_huggingface_papers(source.id, source.keywords)
    return fetch_rss(source.id, source.url, source.category, use_curl=source.useCurl)
