from __future__ import annotations

from datetime import datetime

import httpx

CLASSIFICATION_CN = {
    "Extreme Fear": "极度恐慌",
    "Fear": "恐慌",
    "Neutral": "中性",
    "Greed": "贪婪",
    "Extreme Greed": "极度贪婪",
}


def fetch_crypto_fear_greed() -> dict | None:
    try:
        res = httpx.get("https://api.alternative.me/fng/?limit=1", headers={"User-Agent": "Mozilla/5.0 (DailyBriefBot)"}, timeout=15)
        if res.status_code >= 400:
            return None
        item = (res.json().get("data") or [None])[0]
        if not item or not item.get("value"):
            return None
        classification = item.get("value_classification") or "Neutral"
        return {
            "value": int(item["value"]),
            "classification": classification,
            "classificationCn": CLASSIFICATION_CN.get(classification, classification),
            "timestamp": datetime.fromtimestamp(int(item["timestamp"])).isoformat() if item.get("timestamp") else datetime.utcnow().isoformat(),
        }
    except Exception:
        return None
