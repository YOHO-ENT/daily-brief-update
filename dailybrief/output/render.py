from __future__ import annotations

import html
import math
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from dailybrief.models import ArticleInput, Category, SourceDef
from dailybrief.sources.v2ex import V2EX_OFF_TOPIC_RE
from dailybrief.trading.watchlist import ASSET_GROUP_ORDER, get_asset_group_labels
from dailybrief.utils import get_report_tz, report_locale

TEXTS_ZH = {
    "siteTitle": "每日简报",
    "catTech": "技术动态",
    "catFinance": "财经要点",
    "catPolitics": "时政观察",
    "catTrading": "市场行情",
    "catCommunity": "社区讨论",
    "summaryLabelNews": "中文摘要",
    "summaryLabelIntro": "中文介绍",
    "emptySource": "该源今日无内容。",
    "emptyCategory": "该分类今日无内容。",
    "footer": "内容均来自原媒体，本站仅作摘要整理与回链。",
    "mdTodayOverview": "今日总览",
    "mdEditorNote": "编辑短评",
    "mdTodayKeywords": "今日关键词",
    "mdImportance": "重要度",
    "tradingMarketOverview": "市场总览",
    "tradingTodayFocus": "今日关注",
    "tradingAllAssets": "全部资产",
    "tradingRiskCaveat": "风险提示",
    "archiveLink": "← 历史归档",
}
TEXTS_EN = {
    "siteTitle": "Daily Brief",
    "catTech": "Tech",
    "catFinance": "Finance",
    "catPolitics": "World",
    "catTrading": "Markets",
    "catCommunity": "Community",
    "summaryLabelNews": "Summary",
    "summaryLabelIntro": "Summary",
    "emptySource": "No content from this source today.",
    "emptyCategory": "No content in this category today.",
    "footer": "Content sourced from original publishers; this site provides summary and backlinks only.",
    "mdTodayOverview": "Today's Overview",
    "mdEditorNote": "Editor's Note",
    "mdTodayKeywords": "Keywords",
    "mdImportance": "Importance",
    "tradingMarketOverview": "Market Overview",
    "tradingTodayFocus": "Today's Focus",
    "tradingAllAssets": "All Assets",
    "tradingRiskCaveat": "Risk Disclaimer",
    "archiveLink": "← Archive",
}

STR = TEXTS_EN if report_locale() == "en" else TEXTS_ZH

SUBCATEGORY_ORDER: dict[Category, list[str]] = {
    "tech": ["github-trending", "trending-papers", "x-viral", "ai-news", "cn-community", "overseas-community"],
    "finance": ["news"],
    "politics": ["world"],
}
TECH_MAIN_SUBS = {"github-trending", "trending-papers", "x-viral", "ai-news"}
TECH_COMMUNITY_SUBS = {"cn-community", "overseas-community"}
SUBCATEGORY_LABELS = {
    "github-trending": "GitHub Trending",
    "trending-papers": "热门论文" if report_locale() == "zh" else "Trending Papers",
    "x-viral": "X 推文" if report_locale() == "zh" else "X Viral",
    "ai-news": "AI 媒体" if report_locale() == "zh" else "AI Media",
    "cn-community": "中文社区" if report_locale() == "zh" else "Chinese Community",
    "overseas-community": "海外社区" if report_locale() == "zh" else "Overseas Community",
    "news": "财经新闻" if report_locale() == "zh" else "Finance News",
    "world": "国际要闻" if report_locale() == "zh" else "World News",
}
SOURCE_DISPLAY_LIMITS = {
    "tech:github-trending": 20,
    "tech:cn-community": 10,
    "tech:x-viral": 20,
    "tech:trending-papers": 20,
}
MERGED_SUBGROUP_LIMITS = {"tech:ai-news": 15, "finance:news": 12, "politics:world": 15}
PRESERVE_FETCH_ORDER_SOURCES = {"attentionvc-ai", "huggingface-papers"}
POLITICS_SPORTS_RE = re.compile(
    r"\b(World\s*Cup|Olympics?|UEFA|FIFA|NBA|NFL|NHL|MLB|ATP|WTA|Premier\s*League|Bundesliga|La\s*Liga|Serie\s*A|Champions\s*League|Eurovision|Wimbledon|Grand\s*Slam|F1|Formula\s*1|Ronaldo|Messi|Mbappe|Beckham|Lukaku|Mitoma|sportsman|footballer|squad)\b|世界杯|奥运|残奥|冬奥|欧冠|英超|西甲|意甲|德甲|网球|足球|篮球|高尔夫|棒球|板球|橄榄球",
    re.I,
)


def _obj_to_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    return dict(obj)


def is_sports_article(title: str) -> bool:
    return bool(POLITICS_SPORTS_RE.search(title))


def _published_ts(article: ArticleInput | dict) -> float:
    value = article["publishedAt"] if isinstance(article, dict) else article.publishedAt
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0
    return 0


def _display_limit(category: str, sub_id: str | None) -> int | None:
    if not sub_id:
        return None
    return SOURCE_DISPLAY_LIMITS.get(f"{category}:{sub_id}")


def _merged_limit(category: str, sub_id: str) -> int | None:
    return MERGED_SUBGROUP_LIMITS.get(f"{category}:{sub_id}")


def group_raw(articles: list[ArticleInput], registry: list[SourceDef]) -> dict[str, list[dict]]:
    subcat_of = {s.id: s.subcategory for s in registry}
    enabled_ids = {s.id for s in registry if s.enabled is not False}
    buckets: dict[str, dict[str, dict[str, Any]]] = {"tech": {}, "finance": {}, "politics": {}}
    for s in registry:
        if s.enabled is False:
            continue
        buckets[s.category].setdefault(s.id, {"sourceName": s.name, "items": []})
    for article in articles:
        a = _obj_to_dict(article)
        if a["sourceId"] not in enabled_ids:
            continue
        if a["category"] == "politics" and is_sports_article(a["title"]):
            continue
        if a["sourceId"] in {"v2ex-hot", "linuxdo"} and V2EX_OFF_TOPIC_RE.search(a["title"]):
            continue
        bucket = buckets[a["category"]].setdefault(a["sourceId"], {"sourceName": a.get("source", ""), "items": []})
        bucket["items"].append(a)
    for cat_map in buckets.values():
        for source_id, bucket in cat_map.items():
            if source_id in PRESERVE_FETCH_ORDER_SOURCES:
                continue
            bucket["items"].sort(key=_published_ts, reverse=True)

    def sort_by_registry(groups: list[dict]) -> list[dict]:
        order = {s.id: i for i, s in enumerate(registry)}
        return sorted(groups, key=lambda g: order.get(g["sourceId"], 9999))

    def to_source_group(source_id: str, bucket: dict, limit: int | None) -> dict:
        items = bucket["items"][:limit] if limit else bucket["items"]
        return {"sourceId": source_id, "sourceName": bucket["sourceName"], "items": items}

    out = {"tech": [], "finance": [], "politics": []}
    for cat, cat_map in buckets.items():
        for sub_id in SUBCATEGORY_ORDER.get(cat, []):
            merge_limit = _merged_limit(cat, sub_id)
            if merge_limit is not None:
                flat: list[dict] = []
                for source_id, bucket in cat_map.items():
                    if subcat_of.get(source_id) == sub_id:
                        flat.extend(bucket["items"])
                if not flat:
                    continue
                flat.sort(key=_published_ts, reverse=True)
                out[cat].append(
                    {
                        "id": sub_id,
                        "name": SUBCATEGORY_LABELS.get(sub_id, sub_id),
                        "sources": [
                            {
                                "sourceId": "_merged",
                                "sourceName": SUBCATEGORY_LABELS.get(sub_id, sub_id),
                                "items": flat[:merge_limit],
                                "merged": True,
                            }
                        ],
                    }
                )
                continue
            limit = _display_limit(cat, sub_id)
            groups = [
                to_source_group(source_id, bucket, limit)
                for source_id, bucket in cat_map.items()
                if subcat_of.get(source_id) == sub_id
            ]
            if groups:
                out[cat].append({"id": sub_id, "name": SUBCATEGORY_LABELS.get(sub_id, sub_id), "sources": sort_by_registry(groups)})
    return out


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def format_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if not isinstance(value, datetime):
        return ""
    return value.strftime("%m/%d %H:%M")


def _render_article(article: dict, show_source: bool = False) -> str:
    title = esc(article.get("title"))
    url = esc(article.get("url"))
    excerpt = esc(article.get("excerpt") or "")
    summary = esc(article.get("summary") or article.get("cnSummary") or "")
    meta = esc(article.get("meta") or "")
    time = format_date(article.get("publishedAt"))
    meta_parts = []
    if show_source and article.get("source"):
        meta_parts.append(esc(article.get("source")))
    if time:
        meta_parts.append(esc(time))
    summary_label = STR["summaryLabelNews"] if article.get("category") in {"finance", "politics"} else STR["summaryLabelIntro"]
    return f"""<article class="article">
  <h3><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
  {f'<p class="article-stats">{meta}</p>' if meta else ''}
  {f'<p class="muted">{" · ".join(meta_parts)}</p>' if meta_parts else ''}
  {f'<p>{excerpt}</p>' if excerpt else ''}
  {f'<p class="summary"><b>{esc(summary_label)}</b> {summary}</p>' if summary else ''}
</article>"""


def _render_source_tabs(category: str, sub_id: str, sources: list[dict]) -> str:
    if len(sources) < 2:
        return ""
    return '<nav class="source-tabs">' + "".join(
        f'<button class="source-tab{" active" if i == 0 else ""}" data-source="{esc(s["sourceId"])}" data-sub="{esc(sub_id)}" data-cat="{category}">{esc(s["sourceName"])} <span>{len(s["items"])}</span></button>'
        for i, s in enumerate(sources)
    ) + "</nav>"


def _render_sub_content(category: str, sub: dict, active: bool) -> str:
    source_contents = []
    for i, source in enumerate(sub["sources"]):
        articles = (
            f'<p class="empty">{esc(STR["emptySource"])}</p>'
            if not source["items"]
            else "\n".join(_render_article(a, source.get("merged") is True) for a in source["items"])
        )
        source_contents.append(
            f'<div class="source-content{" active" if i == 0 else ""}" data-source-content="{esc(source["sourceId"])}" data-sub="{esc(sub["id"])}" data-cat="{category}">{articles}</div>'
        )
    return f"""<div class="sub-content{' active' if active else ''}" data-sub-content="{esc(sub['id'])}" data-cat="{category}">
{_render_source_tabs(category, sub['id'], sub['sources'])}
<div class="source-contents">{''.join(source_contents)}</div>
</div>"""


def _render_raw_category(category: str, subs: list[dict]) -> str:
    if not subs:
        return f'<p class="empty">{esc(STR["emptyCategory"])}</p>'
    if len(subs) == 1:
        return _render_sub_content(category, subs[0], True)
    tabs = "".join(
        f'<button class="sub-tab{" active" if i == 0 else ""}" data-sub="{esc(s["id"])}" data-cat="{category}">{esc(s["name"])} <span>{sum(len(src["items"]) for src in s["sources"])}</span></button>'
        for i, s in enumerate(subs)
    )
    panels = "".join(_render_sub_content(category, s, i == 0) for i, s in enumerate(subs))
    return f'<nav class="sub-tabs">{tabs}</nav><div class="sub-contents">{panels}</div>'


def _brief_rank_class(n: Any) -> str:
    try:
        v = float(n)
    except Exception:
        v = 0
    if v >= 8:
        return "high"
    if v >= 6:
        return "mid"
    return "low"


def _render_digest_section(title: str, briefs: list[dict]) -> str:
    if not briefs:
        return ""
    cards = []
    for item in briefs:
        imp = item.get("importance", 0)
        cards.append(
            f"""<article class="brief">
  <div class="brief-head"><span>{esc(item.get('source'))}</span><span class="rank {_brief_rank_class(imp)}">{esc(imp)}/10</span></div>
  <h3><a href="{esc(item.get('url'))}" target="_blank" rel="noopener noreferrer">{esc(item.get('title'))}</a></h3>
  <p>{esc(item.get('summary'))}</p>
</article>"""
        )
    return f'<section class="digest-category"><h2>{esc(title)}</h2><div class="brief-list">{"".join(cards)}</div></section>'


def _fmt_num(n: Any, dp: int = 2) -> str:
    try:
        return f"{float(n):,.{dp}f}"
    except Exception:
        return "—"


def _render_trading_panel(trading: dict) -> str:
    labels = get_asset_group_labels()
    tickers = trading.get("tickers") or []
    widgets = []
    fg = trading.get("crypto_fear_greed")
    if fg:
        widgets.append(f'<div class="widget"><b>Fear/Greed</b><span>{esc(fg.get("value"))} · {esc(fg.get("classificationCn") or fg.get("classification"))}</span></div>')
    cg = trading.get("crypto_global")
    if cg:
        widgets.append(f'<div class="widget"><b>Crypto Cap</b><span>${_fmt_num((cg.get("totalMarketCapUsd") or 0) / 1e12, 2)}T · BTC {_fmt_num(cg.get("btcDominance"), 1)}%</span></div>')
    picks = "".join(
        f'<article class="pick"><b>{esc(p.get("display_name") or p.get("symbol"))}</b><span>{esc(p.get("stance"))}</span><p>{esc(p.get("rationale"))}</p></article>'
        for p in trading.get("watchlist", [])
    )
    group_tabs = "".join(
        f'<button class="asset-tab{" active" if i == 0 else ""}" data-asset="{g}">{esc(labels[g])}</button>'
        for i, g in enumerate(ASSET_GROUP_ORDER)
    )
    group_panels = []
    for i, group in enumerate(ASSET_GROUP_ORDER):
        cards = []
        for t in [x for x in tickers if x.get("group") == group]:
            sigs = " ".join(f'<span class="chip">{esc(s.get("label"))}</span>' for s in t.get("signals", [])[:4])
            cards.append(
                f"""<article class="ticker">
  <h3>{esc(t.get('displayName'))} <small>{esc(t.get('symbol'))}</small></h3>
  <p class="price">{_fmt_num(t.get('currentPrice'))} {esc(t.get('currency'))}</p>
  <p>1d {_fmt_num(t.get('pct1Day'))}% · 5d {_fmt_num(t.get('pct5Day'))}% · RSI {_fmt_num(t.get('rsi14'), 1)}</p>
  <p>Trend {esc(t.get('trend'))} · MACD {_fmt_num(t.get('macd'), 4)} / {_fmt_num(t.get('macdSignal'), 4)}</p>
  <p>{sigs}</p>
</article>"""
            )
        content = "".join(cards) if cards else '<p class="empty">No data.</p>'
        active = " active" if i == 0 else ""
        group_panels.append(
            f'<div class="asset-content{active}" data-asset-content="{group}">{content}</div>'
        )
    return f"""<section class="trading">
<h2>{esc(STR["tradingMarketOverview"])}</h2>
<p class="overview-text">{esc(trading.get("market_overview"))}</p>
<div class="widgets">{''.join(widgets)}</div>
<h2>{esc(STR["tradingTodayFocus"])}</h2>
<div class="picks">{picks}</div>
<h2>{esc(STR["tradingAllAssets"])}</h2>
<nav class="asset-tabs">{group_tabs}</nav>
{''.join(group_panels)}
<h2>{esc(STR["tradingRiskCaveat"])}</h2>
<p class="muted">{esc(trading.get("risk_caveat"))}</p>
</section>"""


def render_html(report: dict, raw: dict, date: str) -> str:
    trading = report.get("trading")
    tech_main = [s for s in raw.get("tech", []) if s["id"] in TECH_MAIN_SUBS]
    tech_community = [s for s in raw.get("tech", []) if s["id"] in TECH_COMMUNITY_SUBS]
    counts = {
        "tech": sum(len(src["items"]) for sg in tech_main for src in sg["sources"]),
        "finance": sum(len(src["items"]) for sg in raw.get("finance", []) for src in sg["sources"]),
        "politics": sum(len(src["items"]) for sg in raw.get("politics", []) for src in sg["sources"]),
        "community": sum(len(src["items"]) for sg in tech_community for src in sg["sources"]),
    }
    tabs = [
        ("tech", STR["catTech"], counts["tech"]),
        *([("trading", STR["catTrading"], len(trading.get("tickers") or []))] if trading else []),
        ("politics", STR["catPolitics"], counts["politics"]),
        ("finance", STR["catFinance"], counts["finance"]),
        *([("community", STR["catCommunity"], counts["community"])] if tech_community else []),
    ]
    tab_html = "".join(
        f'<button class="tab{" active" if i == 0 else ""}" data-panel="{key}">{esc(label)} <span>{count}</span></button>'
        for i, (key, label, count) in enumerate(tabs)
    )
    panels = [
        f'<section class="panel active" data-panel-content="tech">{_render_digest_section(STR["catTech"], report.get("tech_briefs") or [])}{_render_raw_category("tech", tech_main)}</section>'
    ]
    if trading:
        panels.append(f'<section class="panel" data-panel-content="trading">{_render_trading_panel(trading)}</section>')
    panels.append(f'<section class="panel" data-panel-content="politics">{_render_digest_section(STR["catPolitics"], report.get("politics_briefs") or [])}{_render_raw_category("politics", raw.get("politics", []))}</section>')
    panels.append(f'<section class="panel" data-panel-content="finance">{_render_digest_section(STR["catFinance"], report.get("finance_briefs") or [])}{_render_raw_category("finance", raw.get("finance", []))}</section>')
    if tech_community:
        panels.append(f'<section class="panel" data-panel-content="community">{_render_raw_category("tech", tech_community)}</section>')
    keywords = "".join(f'<span class="keyword">{esc(k)}</span>' for k in report.get("keywords", []))
    return f"""<!doctype html>
<html lang="{'en' if report_locale() == 'en' else 'zh-CN'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(STR["siteTitle"])} · {esc(date)}</title>
<style>
:root {{ color-scheme: light dark; --bg:#fafaf9; --fg:#18181b; --muted:#71717a; --rule:#e4e4e7; --card:#fff; --soft:#f4f4f5; --link:#1d4ed8; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0a0a0a; --fg:#fafafa; --muted:#a1a1aa; --rule:#27272a; --card:#18181b; --soft:#27272a; --link:#93c5fd; }} }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--fg); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif; line-height:1.6; }}
main {{ max-width:960px; margin:0 auto; padding:2.5rem 1.5rem 4rem; }} a {{ color:inherit; }} .muted,.article-stats {{ color:var(--muted); font-size:.86rem; }}
.hero-card,.overview-card,.brief,.ticker,.pick,.widget {{ background:var(--card); border:1px solid var(--rule); border-radius:.5rem; padding:1rem; }}
.hero-card {{ border-left:4px solid var(--fg); }} .overview-card {{ margin-top:.8rem; background:var(--soft); }} .overview-text {{ color:var(--muted); }}
.tabs,.sub-tabs,.source-tabs,.asset-tabs {{ display:flex; flex-wrap:wrap; gap:.35rem; margin:1rem 0; border-bottom:1px solid var(--rule); }}
button {{ font:inherit; cursor:pointer; border:1px solid var(--rule); background:var(--soft); color:var(--fg); border-radius:.45rem; padding:.45rem .8rem; }}
button.active {{ background:var(--fg); color:var(--bg); }} .panel,.sub-content,.source-content,.asset-content {{ display:none; }} .panel.active,.sub-content.active,.source-content.active,.asset-content.active {{ display:block; }}
.brief-list,.picks,.widgets {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:.7rem; }} .brief-head {{ display:flex; justify-content:space-between; color:var(--muted); font-size:.8rem; }}
.rank,.keyword,.chip {{ display:inline-block; border-radius:999px; background:var(--soft); padding:.15rem .5rem; font-size:.78rem; }} .rank.high {{ color:#b91c1c; }} .rank.mid {{ color:#92400e; }}
.article {{ padding:1rem 0; border-bottom:1px solid var(--rule); }} .summary {{ background:var(--soft); padding:.7rem; border-radius:.45rem; }} .keyword {{ margin:.2rem; }}
.ticker small {{ color:var(--muted); }} .price {{ font-size:1.2rem; font-weight:700; }} footer {{ margin-top:2rem; color:var(--muted); font-size:.85rem; }}
</style>
</head>
<body>
<main>
<header>
  <a class="muted" href="../archive.html">{esc(STR["archiveLink"])}</a>
  <p class="muted">{esc(date)}</p>
  <h1>{esc(STR["siteTitle"])}</h1>
  <div class="hero-card"><p>{esc(report.get("hero_headline"))}</p></div>
  <div class="overview-card"><b>{esc(STR["mdTodayOverview"])}</b><p class="overview-text">{esc(report.get("daily_overview"))}</p></div>
  <div>{keywords}</div>
</header>
<nav class="tabs">{tab_html}</nav>
{''.join(panels)}
<section class="overview-card"><b>{esc(STR["mdEditorNote"])}</b><p>{esc(report.get("editor_note"))}</p></section>
<footer>{esc(STR["footer"])}</footer>
</main>
<script>
document.addEventListener('click', (e) => {{
  const btn = e.target.closest('button'); if (!btn) return;
  const panel = btn.dataset.panel, sub = btn.dataset.sub, source = btn.dataset.source, asset = btn.dataset.asset;
  if (panel) {{ document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active', b===btn)); document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active', p.dataset.panelContent===panel)); }}
  if (sub) {{ const cat=btn.dataset.cat; document.querySelectorAll(`.sub-tab[data-cat="${{cat}}"]`).forEach(b=>b.classList.toggle('active', b===btn)); document.querySelectorAll(`.sub-content[data-cat="${{cat}}"]`).forEach(p=>p.classList.toggle('active', p.dataset.subContent===sub)); }}
  if (source) {{ const cat=btn.dataset.cat, s=btn.dataset.sub; document.querySelectorAll(`.source-tab[data-cat="${{cat}}"][data-sub="${{s}}"]`).forEach(b=>b.classList.toggle('active', b===btn)); document.querySelectorAll(`.source-content[data-cat="${{cat}}"][data-sub="${{s}}"]`).forEach(p=>p.classList.toggle('active', p.dataset.sourceContent===source)); }}
  if (asset) {{ document.querySelectorAll('.asset-tab').forEach(b=>b.classList.toggle('active', b===btn)); document.querySelectorAll('.asset-content').forEach(p=>p.classList.toggle('active', p.dataset.assetContent===asset)); }}
}});
</script>
</body>
</html>"""


def _importance(value: Any) -> int:
    try:
        f = float(value)
        return int(f) if math.isfinite(f) else 0
    except Exception:
        return 0


def render_markdown(report: dict, date: str) -> str:
    lines = [f"# {STR['siteTitle']} · {date}", ""]
    if report.get("hero_headline"):
        lines += [f"> {report['hero_headline']}", ""]
    if report.get("daily_overview"):
        lines += [f"## {STR['mdTodayOverview']}", "", str(report["daily_overview"]), ""]
    for title, key in [(STR["catTech"], "tech_briefs"), (STR["catFinance"], "finance_briefs"), (STR["catPolitics"], "politics_briefs")]:
        items = report.get(key) or []
        if not items:
            continue
        lines += [f"## {title}", ""]
        for item in items:
            lines += [
                f"### [{item.get('title', '')}]({item.get('url', '')})",
                "",
                f"{item.get('source', '')} · {STR['mdImportance']} {_importance(item.get('importance'))}/10",
                "",
                str(item.get("summary", "")),
                "",
            ]
    if report.get("editor_note"):
        lines += [f"## {STR['mdEditorNote']}", "", str(report["editor_note"]), ""]
    if report.get("keywords"):
        lines += [f"## {STR['mdTodayKeywords']}", "", " · ".join(map(str, report["keywords"])), ""]
    return "\n".join(lines)
