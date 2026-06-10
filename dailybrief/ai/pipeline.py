from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from dailybrief.models import ArticleInput, Category
from dailybrief.runtime.safety import safe_error
from dailybrief.utils import LOG_DIR, json_default, report_locale

from .json_util import extract_json, repair_json_text
from .llm import run_llm
from .prompts import digest_system_prompt

PER_CATEGORY_LIMIT: dict[Category, int] = {"tech": 25, "finance": 20, "politics": 15}
MAX_AGE_DAYS = 14


def select_round_robin(items: list[ArticleInput], limit: int) -> list[ArticleInput]:
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    fresh = [it for it in items if it.publishedAt is None or it.publishedAt.replace(tzinfo=None) >= cutoff]
    by_source: dict[str, list[ArticleInput]] = {}
    for it in fresh:
        by_source.setdefault(it.sourceId, []).append(it)
    for bucket in by_source.values():
        bucket.sort(key=lambda x: x.publishedAt.timestamp() if x.publishedAt else 0, reverse=True)
    buckets = list(by_source.values())
    out: list[ArticleInput] = []
    made_progress = True
    while len(out) < limit and made_progress:
        made_progress = False
        for bucket in buckets:
            if not bucket:
                continue
            out.append(bucket.pop(0))
            made_progress = True
            if len(out) >= limit:
                break
    return out


def _parse_report(text: str) -> dict[str, Any]:
    cleaned = extract_json(text)
    try:
        parsed = json.loads(cleaned)
    except Exception:
        parsed = json.loads(repair_json_text(cleaned))
    return {
        "hero_headline": parsed.get("hero_headline") or "",
        "daily_overview": parsed.get("daily_overview") or "",
        "tech_briefs": parsed.get("tech_briefs") or [],
        "finance_briefs": parsed.get("finance_briefs") or [],
        "politics_briefs": parsed.get("politics_briefs") or [],
        "editor_note": parsed.get("editor_note") or "",
        "keywords": parsed.get("keywords") or [],
    }


def _dump_bad_json(text: str, cleaned: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        (LOG_DIR / f"claude-raw-{ts}.txt").write_text(text, encoding="utf-8")
        (LOG_DIR / f"claude-cleaned-{ts}.txt").write_text(cleaned, encoding="utf-8")
    except Exception:
        pass


def _call_once(payload_json: str) -> dict[str, Any]:
    if report_locale() == "en":
        user_prompt = "\n".join(
            [
                "**Output language: ENGLISH ONLY.** Every string value in the JSON must be written entirely in English.",
                "Your task: generate today's daily brief from the candidate news below. The response MUST be one valid JSON object.",
                "Required fields: hero_headline, daily_overview, tech_briefs, finance_briefs, politics_briefs, editor_note, keywords.",
                "BriefItem fields: title, url copied verbatim from candidate, source, summary, importance.",
                f"Candidate news (JSON array, {len(payload_json)} chars):",
                payload_json,
            ]
        )
    else:
        user_prompt = "\n".join(
            [
                "你的任务：根据下方候选新闻生成当日简报，响应必须是一个合法 JSON 对象，不要 markdown。",
                "JSON 必须包含 hero_headline, daily_overview, tech_briefs, finance_briefs, politics_briefs, editor_note, keywords。",
                "BriefItem 字段：title、url（必须从候选条目原样选取）、source、summary、importance(1-10)。",
                f"候选新闻（JSON 数组，共 {len(payload_json)} 字符）：",
                payload_json,
            ]
        )
    result = run_llm(digest_system_prompt(), user_prompt)
    try:
        return _parse_report(result.text)
    except Exception:
        _dump_bad_json(result.text, extract_json(result.text))
        raise


def generate_daily_report(articles: list[ArticleInput]) -> dict[str, Any]:
    grouped: dict[Category, list[ArticleInput]] = {"tech": [], "finance": [], "politics": []}
    for article in articles:
        grouped[article.category].append(article)
    compact: list[ArticleInput] = []
    for category, items in grouped.items():
        compact.extend(select_round_robin(items, PER_CATEGORY_LIMIT[category]))
    payload = [
        {
            "n": i + 1,
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "category": a.category,
            "excerpt": (a.excerpt or "")[:200],
            "published": a.publishedAt.isoformat() if a.publishedAt else "",
        }
        for i, a in enumerate(compact)
    ]
    payload_json = json.dumps(payload, ensure_ascii=False, default=json_default)
    try:
        return _call_once(payload_json)
    except Exception as exc:
        print(f"[pipeline] first LLM call failed, retrying: {safe_error(exc)}")
        return _call_once(payload_json)
