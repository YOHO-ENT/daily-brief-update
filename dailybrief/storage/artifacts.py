from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dailybrief.models import ArticleInput, RawArticle
from dailybrief.utils import OUTPUT_DIR, parse_dt, read_json, write_json


@dataclass(frozen=True)
class ArtifactPaths:
    date: str
    directory: Path
    report_json: Path
    articles_json: Path
    html: Path
    markdown: Path

    def to_dict(self) -> dict[str, str]:
        out = {
            "directory": str(self.directory),
            "json": str(self.report_json),
            "articles": str(self.articles_json),
            "html": str(self.html),
        }
        if self.markdown.exists():
            out["markdown"] = str(self.markdown)
        return out


def output_root(output_dir: Path | str | None = None) -> Path:
    return Path(output_dir) if output_dir is not None else OUTPUT_DIR


def paths_for_date(date: str, output_dir: Path | str | None = None) -> ArtifactPaths:
    root = output_root(output_dir)
    directory = root / date
    base = directory / date
    return ArtifactPaths(
        date=date,
        directory=directory,
        report_json=base.with_suffix(".json"),
        articles_json=Path(f"{base}-articles.json"),
        html=base.with_suffix(".html"),
        markdown=base.with_suffix(".md"),
    )


def article_to_input(raw: RawArticle, source_name: str) -> ArticleInput:
    return ArticleInput(
        sourceId=raw.sourceId,
        title=raw.title,
        url=raw.url,
        excerpt=raw.excerpt,
        publishedAt=raw.publishedAt,
        category=raw.category,
        summary=raw.summary,
        meta=raw.meta,
        source=source_name,
    )


def article_from_json(data: dict[str, Any]) -> ArticleInput:
    return ArticleInput(
        sourceId=data["sourceId"],
        title=data["title"],
        url=data["url"],
        excerpt=data.get("excerpt"),
        publishedAt=parse_dt(data.get("publishedAt")),
        category=data["category"],
        summary=data.get("summary") or data.get("cnSummary"),
        meta=data.get("meta"),
        source=data.get("source", ""),
    )


def load_report(date: str, output_dir: Path | str | None = None) -> dict[str, Any]:
    paths = paths_for_date(date, output_dir)
    if not paths.report_json.exists():
        raise FileNotFoundError(f"Report JSON not found: {paths.report_json}")
    data = read_json(paths.report_json)
    if not isinstance(data, dict):
        raise ValueError(f"Report JSON must be an object: {paths.report_json}")
    return data


def load_articles(date: str, output_dir: Path | str | None = None) -> list[ArticleInput]:
    paths = paths_for_date(date, output_dir)
    if not paths.articles_json.exists():
        raise FileNotFoundError(f"Articles sidecar not found: {paths.articles_json}")
    data = read_json(paths.articles_json)
    if not isinstance(data, dict):
        raise ValueError(f"Articles sidecar must be an object: {paths.articles_json}")
    return [article_from_json(a) for a in data.get("articles", [])]


def write_report_outputs(
    date: str,
    report: dict[str, Any],
    articles: list[ArticleInput],
    output_dir: Path | str | None = None,
) -> ArtifactPaths:
    from dailybrief.output.render import group_raw, render_html, render_markdown
    from dailybrief.sources.registry import sources

    paths = paths_for_date(date, output_dir)
    paths.directory.mkdir(parents=True, exist_ok=True)
    raw = group_raw(articles, sources)
    write_json(paths.report_json, report)
    write_json(paths.articles_json, {"date": date, "articles": articles})
    paths.html.write_text(render_html(report, raw, date), encoding="utf-8")
    if os.environ.get("OUTPUT_MARKDOWN") == "true":
        paths.markdown.write_text(render_markdown(report, date), encoding="utf-8")
    return paths


def latest_report_date(output_dir: Path | str | None = None) -> str | None:
    root = output_root(output_dir)
    if not root.exists():
        return None
    dates = sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and len(p.name) == 10 and (p / f"{p.name}.html").exists()
    )
    return dates[-1] if dates else None


def report_url(date: str, output_dir: Path | str | None = None, base_url: str | None = None) -> str:
    paths = paths_for_date(date, output_dir)
    if base_url:
        return f"{base_url.rstrip('/')}/{date}/{date}.html"
    return paths.html.resolve().as_uri()

