from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dailybrief.utils import report_locale

AssetGroup = Literal["us-equity", "crypto", "china-equity", "commodity-fx", "macro"]


@dataclass(frozen=True)
class TickerDef:
    symbol: str
    displayName: str
    group: AssetGroup
    displayNameEn: str | None = None


ASSET_GROUP_ORDER: list[AssetGroup] = ["macro", "us-equity", "crypto", "china-equity", "commodity-fx"]

ASSET_GROUP_LABELS_ZH = {
    "us-equity": "美股 / ETF",
    "crypto": "加密货币",
    "china-equity": "中概 / 港股",
    "commodity-fx": "商品 / 外汇",
    "macro": "宏观信号",
}
ASSET_GROUP_LABELS_EN = {
    "us-equity": "US Stocks / ETF",
    "crypto": "Crypto",
    "china-equity": "China / HK",
    "commodity-fx": "Commodities / FX",
    "macro": "Macro",
}


def get_asset_group_labels(locale: str | None = None) -> dict[str, str]:
    return ASSET_GROUP_LABELS_EN if (locale or report_locale()) == "en" else ASSET_GROUP_LABELS_ZH


def get_display_name(t: TickerDef, locale: str | None = None) -> str:
    return (t.displayNameEn or t.displayName) if (locale or report_locale()) == "en" else t.displayName


WATCHLIST: list[TickerDef] = [
    TickerDef("SPY", "S&P 500 ETF", "us-equity"),
    TickerDef("QQQ", "Nasdaq 100 ETF", "us-equity"),
    TickerDef("AAPL", "Apple", "us-equity"),
    TickerDef("MSFT", "Microsoft", "us-equity"),
    TickerDef("NVDA", "Nvidia", "us-equity"),
    TickerDef("GOOGL", "Alphabet", "us-equity"),
    TickerDef("TSLA", "Tesla", "us-equity"),
    TickerDef("META", "Meta", "us-equity"),
    TickerDef("BTC-USD", "Bitcoin", "crypto"),
    TickerDef("ETH-USD", "Ethereum", "crypto"),
    TickerDef("SOL-USD", "Solana", "crypto"),
    TickerDef("BABA", "阿里巴巴 (BABA)", "china-equity", "Alibaba (BABA)"),
    TickerDef("PDD", "拼多多 (PDD)", "china-equity", "Pinduoduo (PDD)"),
    TickerDef("JD", "京东 (JD)", "china-equity", "JD.com (JD)"),
    TickerDef("0700.HK", "腾讯控股 (0700.HK)", "china-equity", "Tencent (0700.HK)"),
    TickerDef("GC=F", "黄金期货", "commodity-fx", "Gold Futures"),
    TickerDef("CL=F", "WTI 原油期货", "commodity-fx", "WTI Crude Futures"),
    TickerDef("USDCNY=X", "美元 / 人民币", "commodity-fx", "USD / CNY"),
    TickerDef("^VIX", "VIX 恐慌指数", "macro", "VIX (Volatility)"),
    TickerDef("^TNX", "10Y 美债收益率 (%)", "macro", "10Y Treasury Yield (%)"),
    TickerDef("DX-Y.NYB", "美元指数 DXY", "macro", "DXY (US Dollar Index)"),
]
