from __future__ import annotations

import json

from dailybrief.utils import report_locale

from .json_util import extract_json, repair_json_text
from .llm import run_llm

SYSTEM_ZH = """你是一名专业、克制、中性的中文技术指标解读员。基于输入技术指标写客观技术状态报告，不提供投资建议，不预测涨跌。
输出严格 JSON：{"market_overview":"...","watchlist":[{"symbol":"...","display_name":"...","stance":"偏上行|偏下行|中性","rationale":"..."}],"risk_caveat":"..."}。
watchlist 必须 3-5 个，必须引用具体指标数字。risk_caveat 必须包含「过去走势不代表未来表现」与「仅供技术指标解读参考」。"""
SYSTEM_EN = """You are a professional, restrained, neutral English technical-indicator interpreter. Write an objective technical-state report, not investment advice.
Output strict JSON: {"market_overview":"...","watchlist":[{"symbol":"...","display_name":"...","stance":"Bullish|Bearish|Neutral","rationale":"..."}],"risk_caveat":"..."}.
watchlist must contain 3-5 complete objects and cite specific indicator numbers. risk_caveat must include "past performance does not guarantee future results" and "for technical-indicator interpretation only"."""


def _round(n: float | int | None, dp: int = 2):
    if n is None:
        return None
    return round(float(n), dp)


def generate_trading_commentary(input_data: dict) -> dict:
    tickers = input_data.get("tickers") or []
    payload = [
        {
            "symbol": a["symbol"],
            "displayName": a["displayName"],
            "group": a["group"],
            "currentPrice": _round(a["currentPrice"]),
            "pct1Day": _round(a["pct1Day"], 2),
            "pct5Day": _round(a["pct5Day"], 2),
            "pct52WeekHigh": _round(a["pct52WeekHigh"], 2),
            "pct52WeekLow": _round(a["pct52WeekLow"], 2),
            "sma20": _round(a.get("sma20")),
            "sma50": _round(a.get("sma50")),
            "sma200": _round(a.get("sma200")),
            "rsi14": _round(a.get("rsi14"), 1),
            "macd": _round(a.get("macd"), 4),
            "macdSignal": _round(a.get("macdSignal"), 4),
            "trend": a.get("trend"),
            "rsiState": a.get("rsiState"),
            "signals": [s.get("label") for s in a.get("signals", [])],
        }
        for a in tickers
    ]
    context_lines: list[str] = []
    fg = input_data.get("cryptoFearGreed")
    if fg:
        classification = fg.get("classification") if report_locale() == "en" else fg.get("classificationCn")
        context_lines.append(
            f"Crypto Fear & Greed Index = {fg.get('value')} ({classification})"
            if report_locale() == "en"
            else f"加密恐慌贪婪指数 = {fg.get('value')}（{classification}）"
        )
    cg = input_data.get("cryptoGlobal")
    if cg:
        context_lines.append(
            f"Crypto total market cap = {cg.get('totalMarketCapUsd', 0) / 1e12:.2f}T USD · BTC dominance {cg.get('btcDominance', 0):.1f}%"
            if report_locale() == "en"
            else f"加密总市值 = {cg.get('totalMarketCapUsd', 0) / 1e12:.2f}T USD · BTC 主导率 {cg.get('btcDominance', 0):.1f}%"
        )

    user_prompt = "\n".join(
        [
            "Output a single valid JSON object. watchlist must contain 3-5 complete objects.",
            "\n".join(f"- {line}" for line in context_lines),
            f"Candidate assets ({len(payload)} entries, JSON array):",
            json.dumps(payload, ensure_ascii=False),
        ]
    )
    fallback = {
        "market_overview": "",
        "watchlist": [],
        "risk_caveat": (
            "The above is based on computed technical indicators from public market data and does NOT constitute investment advice. Past performance does not guarantee future results; for technical-indicator interpretation only."
            if report_locale() == "en"
            else "以上内容基于公开行情数据的技术指标计算，不构成任何投资建议。过去走势不代表未来表现，仅供技术指标解读参考。"
        ),
    }
    system_prompt = SYSTEM_EN if report_locale() == "en" else SYSTEM_ZH
    retry_hint = "\nPrevious attempt was invalid. Return 3-5 complete watchlist objects."
    for attempt in range(3):
        try:
            result = run_llm(system_prompt, user_prompt + (retry_hint if attempt else ""), timeout_ms=240_000)
            cleaned = extract_json(result.text)
            try:
                parsed = json.loads(cleaned)
            except Exception:
                parsed = json.loads(repair_json_text(cleaned))
            overview = parsed.get("market_overview") or ""
            picks = parsed.get("watchlist") or []
            if len(overview) < 100:
                raise ValueError(f"market_overview too short ({len(overview)} chars)")
            if len(picks) < 2:
                raise ValueError(f"watchlist too short ({len(picks)} picks)")
            for pick in picks:
                if not isinstance(pick, dict) or not pick.get("symbol") or not pick.get("stance") or len(str(pick.get("rationale", ""))) < 20:
                    raise ValueError(f"watchlist pick has invalid shape: {str(pick)[:120]}")
            return {
                "market_overview": overview,
                "watchlist": picks,
                "risk_caveat": parsed.get("risk_caveat") or fallback["risk_caveat"],
            }
        except Exception as exc:
            print(f"[trading-commentary] attempt {attempt + 1}/3 failed: {exc}")
    return fallback
