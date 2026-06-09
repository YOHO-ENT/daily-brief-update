from __future__ import annotations

from datetime import datetime
from urllib.parse import quote as url_quote

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def fetch_ticker_data(symbol: str) -> dict | None:
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{url_quote(symbol, safe='')}?range=1y&interval=1d"
    res = httpx.get(url, headers=HEADERS, timeout=20)
    if res.status_code >= 400:
        return None
    data = res.json()
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        return None
    meta = result.get("meta") or {}
    ts = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    candles = []
    for i, stamp in enumerate(ts):
        o = (quote_data.get("open") or [None] * len(ts))[i]
        h = (quote_data.get("high") or [None] * len(ts))[i]
        l = (quote_data.get("low") or [None] * len(ts))[i]
        c = (quote_data.get("close") or [None] * len(ts))[i]
        v = (quote_data.get("volume") or [None] * len(ts))[i]
        if o is None or h is None or l is None or c is None:
            continue
        candles.append({"date": datetime.fromtimestamp(stamp), "open": o, "high": h, "low": l, "close": c, "volume": v or 0})
    if not candles:
        return None
    return {
        "symbol": meta.get("symbol") or symbol,
        "currency": meta.get("currency") or "",
        "exchangeName": meta.get("exchangeName") or "",
        "regularMarketPrice": meta.get("regularMarketPrice") or candles[-1]["close"],
        "fiftyTwoWeekHigh": meta.get("fiftyTwoWeekHigh") or 0,
        "fiftyTwoWeekLow": meta.get("fiftyTwoWeekLow") or 0,
        "candles": candles,
    }
