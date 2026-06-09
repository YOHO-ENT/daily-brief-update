from __future__ import annotations

import httpx


def fetch_crypto_global() -> dict | None:
    try:
        res = httpx.get("https://api.coingecko.com/api/v3/global", headers={"User-Agent": "Mozilla/5.0 (DailyBriefBot)"}, timeout=15)
        if res.status_code >= 400:
            return None
        data = res.json().get("data") or {}
        return {
            "totalMarketCapUsd": data.get("total_market_cap", {}).get("usd", 0),
            "total24hVolumeUsd": data.get("total_volume", {}).get("usd", 0),
            "marketCapChangePct24h": data.get("market_cap_change_percentage_24h_usd", 0),
            "btcDominance": data.get("market_cap_percentage", {}).get("btc", 0),
            "ethDominance": data.get("market_cap_percentage", {}).get("eth", 0),
            "activeCryptocurrencies": data.get("active_cryptocurrencies", 0),
        }
    except Exception:
        return None
