from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from dailybrief.models import ArticleInput
from dailybrief.utils import LOG_DIR, report_locale

from .json_util import extract_json, repair_json_text
from .llm import run_llm

GH_SYSTEM_ZH = """你是一名技术编辑，负责为 GitHub Trending 项目写中文介绍。输出严格 JSON：
{"summaries":[{"url":"<原 url>","summary":"<60-120 字中文介绍>"}]}"""
GH_SYSTEM_EN = """You are a technical editor writing English summaries for GitHub Trending repositories. Output strict JSON:
{"summaries":[{"url":"<exact url>","summary":"<60-120 word English summary>"}]}"""

NEWS_SYSTEM_ZH = """你是一名中文财经/时政/科技编辑，为新闻生成中文事实摘要。保留关键数字、机构、人名、地区；中性事实陈述。输出严格 JSON：
{"summaries":[{"url":"<原 url>","summary":"<50-100 字中文摘要>"}]}"""
NEWS_SYSTEM_EN = """You are an English-language editor producing factual summaries. Preserve key numbers, institutions, people, and regions. Output strict JSON:
{"summaries":[{"url":"<exact url>","summary":"<50-100 word English summary>"}]}"""

XVIRAL_SYSTEM_ZH = """你是一名中文 AI 圈编辑，为 X 上的爆款 AI 帖子生成中文摘要。不要照搬标题，以 previewText 为准。输出严格 JSON：
{"summaries":[{"url":"<原 url>","summary":"<60-100 字中文摘要>"}]}"""
XVIRAL_SYSTEM_EN = """You are an editor producing English summaries of viral AI-related X posts. Do not just rephrase titles; use previewText as source of truth. Output strict JSON:
{"summaries":[{"url":"<exact url>","summary":"<60-100 word English summary>"}]}"""

PAPERS_SYSTEM_ZH = """你是一名 AI 研究方向中文编辑，为 HuggingFace 热门论文写中文摘要。说明问题、方法、贡献。输出严格 JSON：
{"summaries":[{"url":"<原 url>","summary":"<60-110 字中文摘要>"}]}"""
PAPERS_SYSTEM_EN = """You are an AI-research editor writing English summaries of trending HuggingFace papers. Cover problem, method, and contribution. Output strict JSON:
{"summaries":[{"url":"<exact url>","summary":"<60-110 word English summary>"}]}"""


def _prompt_set() -> dict[str, str]:
    if report_locale() == "en":
        return {"gh": GH_SYSTEM_EN, "news": NEWS_SYSTEM_EN, "x": XVIRAL_SYSTEM_EN, "papers": PAPERS_SYSTEM_EN}
    return {"gh": GH_SYSTEM_ZH, "news": NEWS_SYSTEM_ZH, "x": XVIRAL_SYSTEM_ZH, "papers": PAPERS_SYSTEM_ZH}


def _dump_under_count(scope: str, requested: int, returned: int, text: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        tag = "".join(ch if ch.isalnum() else "-" for ch in scope)
        (LOG_DIR / f"enrich-undercount-{tag}-{ts}.txt").write_text(
            f"scope={scope}\nrequested={requested}\nreturned={returned}\n\n--- raw LLM output ---\n{text}",
            encoding="utf-8",
        )
    except Exception:
        pass


def run_enrichment(payload: list[dict], system_prompt: str, scope: str) -> dict[str, str]:
    if not payload:
        return {}
    lang_header = (
        "**Output language: ENGLISH ONLY.** Every summary string must be written entirely in English."
        if report_locale() == "en"
        else "**输出语言：仅中文。** 每个 summary 字段必须全部是中文。"
    )
    user_prompt = "\n".join(
        [
            lang_header,
            "",
            f"Candidate items ({len(payload)} entries, JSON array):",
            json.dumps(payload, ensure_ascii=False),
            "",
            'Output {"summaries": [{"url": ..., "summary": ...}, ...]} — url must be copied exactly from input.',
        ]
    )
    try:
        result = run_llm(system_prompt, user_prompt, timeout_ms=240_000)
        cleaned = extract_json(result.text)
        try:
            parsed = json.loads(cleaned)
        except Exception:
            parsed = json.loads(repair_json_text(cleaned))
        out = {
            str(item["url"]): str(item["summary"]).strip()
            for item in parsed.get("summaries", [])
            if item.get("url") and item.get("summary")
        }
        if len(out) < len(payload) / 2 and len(payload) >= 3:
            _dump_under_count(scope, len(payload), len(out), result.text)
        return out
    except Exception as exc:
        print(f"[enrich] {scope} failed: {exc}")
        return {}


def enrich_github_trending_summaries(items: list[ArticleInput]) -> dict[str, str]:
    payload = [{"url": it.url, "repo": it.title, "description": (it.excerpt or "")[:200]} for it in items]
    return run_enrichment(payload, _prompt_set()["gh"], "GH summaries")


def enrich_news_summaries(items: list[ArticleInput]) -> dict[str, str]:
    payload = [
        {"url": it.url, "title": it.title, "source": it.source, "excerpt": (it.excerpt or "")[:280]}
        for it in items
    ]
    return run_enrichment(payload, _prompt_set()["news"], "news summaries")


def enrich_xviral_summaries(items: list[ArticleInput]) -> dict[str, str]:
    payload = [
        {
            "url": it.url,
            "title": it.title,
            "author": it.url.split("x.com/")[1].split("/")[0] if "x.com/" in it.url else "",
            "previewText": (it.excerpt or "")[:280],
        }
        for it in items
    ]
    return run_enrichment(payload, _prompt_set()["x"], "X-viral summaries")


def enrich_papers_summaries(items: list[ArticleInput]) -> dict[str, str]:
    payload = [{"url": it.url, "title": it.title, "excerpt": (it.excerpt or "")[:300]} for it in items]
    return run_enrichment(payload, _prompt_set()["papers"], "papers summaries")
