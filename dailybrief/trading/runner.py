from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .signals import analyze_ticker
from .watchlist import WATCHLIST, TickerDef
from .yahoo import fetch_ticker_data


def _analyze(defn: TickerDef) -> dict | None:
    try:
        raw = fetch_ticker_data(defn.symbol)
        if not raw:
            print(f"[trading] {defn.symbol} returned no data")
            return None
        return analyze_ticker(defn, raw)
    except Exception as exc:
        print(f"[trading] {defn.symbol} failed: {exc}")
        return None


def analyze_watchlist() -> list[dict]:
    with ThreadPoolExecutor(max_workers=min(8, len(WATCHLIST))) as pool:
        results = list(pool.map(_analyze, WATCHLIST))
    return [r for r in results if r is not None]
