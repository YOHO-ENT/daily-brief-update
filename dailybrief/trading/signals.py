from __future__ import annotations

from .indicators import detect_recent_cross, last, macd as macd_fn, rsi as rsi_fn, sma
from .watchlist import TickerDef, get_display_name

SIGNAL_LABELS = {
    "golden-cross": "金叉(SMA50↑SMA200)",
    "death-cross": "死叉(SMA50↓SMA200)",
    "macd-bull-cross": "MACD 金叉",
    "macd-bear-cross": "MACD 死叉",
    "rsi-overbought": "RSI 超买",
    "rsi-oversold": "RSI 超卖",
    "near-52w-high": "接近 52 周高",
    "near-52w-low": "接近 52 周低",
    "above-sma50-sma200": "多头排列",
    "below-sma50-sma200": "空头排列",
}


def analyze_ticker(defn: TickerDef, raw: dict) -> dict:
    closes = [c["close"] for c in raw["candles"]]
    n = len(closes)
    current = raw["regularMarketPrice"]
    prev1 = closes[n - 2] if n >= 2 else None
    prev5 = closes[n - 6] if n >= 6 else None
    pct1 = ((current - prev1) / prev1) * 100 if prev1 else 0
    pct5 = ((current - prev5) / prev5) * 100 if prev5 else 0
    high = raw.get("fiftyTwoWeekHigh") or 0
    low = raw.get("fiftyTwoWeekLow") or 0
    pct_high = ((current - high) / high) * 100 if high else 0
    pct_low = ((current - low) / low) * 100 if low else 0

    sma20_arr = sma(closes, 20)
    sma50_arr = sma(closes, 50)
    sma200_arr = sma(closes, 200)
    rsi_arr = rsi_fn(closes, 14)
    m = macd_fn(closes)
    sma20_val = last(sma20_arr)
    sma50_val = last(sma50_arr)
    sma200_val = last(sma200_arr)
    rsi14 = last(rsi_arr)
    macd_val = last(m["macd"])
    macd_signal = last(m["signal"])
    macd_hist = last(m["histogram"])

    if sma50_val and sma200_val and current > sma50_val > sma200_val:
        trend = "bullish"
    elif sma50_val and sma200_val and current < sma50_val < sma200_val:
        trend = "bearish"
    else:
        trend = "neutral"

    if rsi14 is not None and rsi14 > 70:
        rsi_state = "overbought"
    elif rsi14 is not None and rsi14 < 30:
        rsi_state = "oversold"
    else:
        rsi_state = "normal"

    signals = []
    if sma50_arr and sma200_arr:
        aligned50 = sma50_arr[-len(sma200_arr) :]
        cross = detect_recent_cross(aligned50, sma200_arr, 10)
        if cross:
            typ = "golden-cross" if cross["direction"] == "up" else "death-cross"
            signals.append({"type": typ, "label": SIGNAL_LABELS[typ], "daysAgo": cross["daysAgo"]})
    if m["macd"] and m["signal"]:
        aligned_macd = m["macd"][-len(m["signal"]) :]
        cross = detect_recent_cross(aligned_macd, m["signal"], 5)
        if cross:
            typ = "macd-bull-cross" if cross["direction"] == "up" else "macd-bear-cross"
            signals.append({"type": typ, "label": SIGNAL_LABELS[typ], "daysAgo": cross["daysAgo"]})
    if rsi_state == "overbought":
        signals.append({"type": "rsi-overbought", "label": SIGNAL_LABELS["rsi-overbought"]})
    elif rsi_state == "oversold":
        signals.append({"type": "rsi-oversold", "label": SIGNAL_LABELS["rsi-oversold"]})
    if pct_high >= -3:
        signals.append({"type": "near-52w-high", "label": SIGNAL_LABELS["near-52w-high"]})
    elif pct_low <= 3:
        signals.append({"type": "near-52w-low", "label": SIGNAL_LABELS["near-52w-low"]})
    if trend == "bullish":
        signals.append({"type": "above-sma50-sma200", "label": SIGNAL_LABELS["above-sma50-sma200"]})
    elif trend == "bearish":
        signals.append({"type": "below-sma50-sma200", "label": SIGNAL_LABELS["below-sma50-sma200"]})

    return {
        "symbol": defn.symbol,
        "displayName": get_display_name(defn),
        "group": defn.group,
        "currency": raw.get("currency", ""),
        "exchangeName": raw.get("exchangeName", ""),
        "currentPrice": current,
        "pct1Day": pct1,
        "pct5Day": pct5,
        "pct52WeekHigh": pct_high,
        "pct52WeekLow": pct_low,
        "sma20": sma20_val,
        "sma50": sma50_val,
        "sma200": sma200_val,
        "rsi14": rsi14,
        "macd": macd_val,
        "macdSignal": macd_signal,
        "macdHistogram": macd_hist,
        "trend": trend,
        "rsiState": rsi_state,
        "signals": signals,
    }
