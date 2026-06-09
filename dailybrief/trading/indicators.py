from __future__ import annotations


def sma(values: list[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        return []
    out = []
    total = sum(values[:period])
    out.append(total / period)
    for i in range(period, len(values)):
        total += values[i] - values[i - period]
        out.append(total / period)
    return out


def ema(values: list[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        return []
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    out = [prev]
    for value in values[period:]:
        prev = (value - prev) * k + prev
        out.append(prev)
    return out


def rsi(closes: list[float], period: int = 14) -> list[float]:
    if len(closes) <= period:
        return []
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = [100 - 100 / (1 + avg_gain / (avg_loss or 1e-10))]
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(100 - 100 / (1 + avg_gain / (avg_loss or 1e-10)))
    return out


def macd(closes: list[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> dict[str, list[float]]:
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    if not slow:
        return {"macd": [], "signal": [], "histogram": []}
    fast_aligned = fast[-len(slow) :]
    macd_line = [f - s for f, s in zip(fast_aligned, slow)]
    signal_line = ema(macd_line, signal_period)
    if not signal_line:
        return {"macd": macd_line, "signal": [], "histogram": []}
    macd_aligned = macd_line[-len(signal_line) :]
    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def detect_recent_cross(fast: list[float], slow: list[float], lookback: int = 5):
    n = min(len(fast), len(slow))
    if n < 2:
        return None
    for i in range(min(lookback, n - 1)):
        idx = n - 1 - i
        today = fast[idx] - slow[idx]
        yesterday = fast[idx - 1] - slow[idx - 1]
        if yesterday <= 0 and today > 0:
            return {"daysAgo": i, "direction": "up"}
        if yesterday >= 0 and today < 0:
            return {"daysAgo": i, "direction": "down"}
    return None


def last(values: list):
    return values[-1] if values else None
