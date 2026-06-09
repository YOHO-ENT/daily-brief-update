from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Category = Literal["tech", "finance", "politics"]
SourceType = Literal["rss", "api", "scrape"]
Locale = Literal["zh", "en"]


@dataclass
class SourceDef:
    id: str
    name: str
    type: SourceType
    url: str
    category: Category
    subcategory: str | None = None
    useCurl: bool | None = None
    enabled: bool | None = None
    lang: Locale | None = None
    locales: list[Locale] | None = None
    notes: str | None = None
    keywords: list[str] | None = None


@dataclass
class RawArticle:
    sourceId: str
    title: str
    url: str
    category: Category
    excerpt: str | None = None
    publishedAt: datetime | None = None
    summary: str | None = None
    meta: str | None = None


@dataclass
class ArticleInput(RawArticle):
    source: str = ""


@dataclass
class BriefItem:
    title: str
    url: str
    source: str
    summary: str
    importance: int


@dataclass
class DailyReport:
    hero_headline: str = ""
    daily_overview: str = ""
    tech_briefs: list[dict[str, Any]] = field(default_factory=list)
    finance_briefs: list[dict[str, Any]] = field(default_factory=list)
    politics_briefs: list[dict[str, Any]] = field(default_factory=list)
    editor_note: str = ""
    keywords: list[str] = field(default_factory=list)
    trading: dict[str, Any] | None = None
