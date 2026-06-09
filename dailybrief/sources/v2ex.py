from __future__ import annotations

import re
from datetime import datetime

import httpx

from dailybrief.models import RawArticle

TECH_NODES = ["programmer", "dev", "python", "golang", "linux", "apple", "rust", "ai"]
V2EX_OFF_TOPIC_RE = re.compile(
    r"(足浴|按摩|捏\s*jio|相亲|对象|男友|女友|分手|婆|岳|家暴|出轨|彩礼|"
    r"9\.9\s*元|抽奖|薅羊毛|代理\s*IP|住宅\s*IP|跨境\s*(卖家|IP|电商)|"
    r"辣椒\s*HTTP|买房|买车|装修|房贷|养老|退休|结婚|生娃|带娃|养娃|"
    r"减肥|健身|租房|搬家|签证|移民|岛主|离职|裸辞|老赖|存款|新人报道|"
    r"无聊|发小|废了|工资|加班吐槽|找工作|失业|找对象)",
    re.I,
)


def _fetch_node(client: httpx.Client, node: str) -> list[dict]:
    try:
        r = client.get(f"https://www.v2ex.com/api/topics/show.json?node_name={node}")
        if r.status_code != 200:
            return []
        return list(r.json() or [])
    except Exception:
        return []


def fetch_v2ex(source_id: str, limit: int = 25) -> list[RawArticle]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DailyBriefBot/1.0)", "Accept": "application/json"}
    candidates: list[tuple[dict, str]] = []
    seen: set[str] = set()
    with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
        for node in TECH_NODES:
            for topic in _fetch_node(client, node):
                title = topic.get("title") or ""
                url = topic.get("url") or ""
                if not title or not url or url in seen:
                    continue
                if V2EX_OFF_TOPIC_RE.search(title) or (topic.get("replies") or 0) == 0:
                    continue
                seen.add(url)
                candidates.append((topic, topic.get("node", {}).get("title") or topic.get("node", {}).get("name") or "?"))
    candidates.sort(key=lambda x: x[0].get("replies") or 0, reverse=True)
    return [
        RawArticle(
            sourceId=source_id,
            title=t.get("title", ""),
            url=t.get("url", ""),
            excerpt=f"{t.get('replies', 0)} 回复 · {node_title} 节点",
            publishedAt=datetime.fromtimestamp(t["created"]) if t.get("created") else None,
            category="tech",
        )
        for t, node_title in candidates[:limit]
    ]
