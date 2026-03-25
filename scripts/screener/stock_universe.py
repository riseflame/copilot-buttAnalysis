"""
股票池动态获取 — 从 Yahoo Finance 全市场数据筛选

不再硬编码标的列表。通过 yf.screen() 直接从交易所全量数据中
按 region + 基础财务条件拉取候选列表。

支持三种模式：
  1. screen_universe()  — 带财务条件的全市场筛选（Level 1 直接使用）
  2. broad_universe()   — 仅按 region 获取宽泛标的列表（用于历史回测等需要 ticker 列表的场景）
  3. get_universe()     — 兼容旧接口，调用 broad_universe()

Ticker 格式：
  A股沪市: {6位代码}.SS   (如 600519.SS)
  A股深市: {6位代码}.SZ   (如 000651.SZ)
  港股:    {4位代码}.HK   (如 0700.HK)
  美股:    直接 ticker    (如 AAPL)
"""

from __future__ import annotations

import yfinance as yf
from yfinance.screener import EquityQuery

# region -> yfinance screener region code
MARKET_REGION = {
    "HK": "hk",
    "A": "cn",
    "US": "us",
}


def screen_universe(
    market: str = "HK",
    max_pb: float = 1.5,
    min_div_yield: float = 0.0,
    max_pe: float = 50.0,
    size: int = 250,
) -> list[dict]:
    """直接从全市场数据中筛选符合条件的标的（Level 1 主入口）。

    使用 Yahoo Finance screener API，一次请求返回最多 250 只。
    无需硬编码股票池。

    Returns:
        [{"ticker": "0160.HK", "name": "漢國置地", "market": "HK",
          "pb": 0.067, "pe": 5.2, "dividend_yield": 3.09,
          "market_cap": 700000000, "roe": 0.05, ...}, ...]
    """
    region = MARKET_REGION.get(market.upper(), market.lower())

    conditions = [
        EquityQuery('eq', ['region', region]),
        EquityQuery('gt', ['pricebookratio.quarterly', 0]),
    ]
    if max_pb < 100:
        conditions.append(EquityQuery('lt', ['pricebookratio.quarterly', max_pb]))
    if min_div_yield > 0:
        conditions.append(EquityQuery('gt', ['forward_dividend_yield', min_div_yield]))
    if max_pe < 9999:
        conditions.append(EquityQuery('gt', ['peratio.lasttwelvemonths', 0]))
        conditions.append(EquityQuery('lt', ['peratio.lasttwelvemonths', max_pe]))

    q = EquityQuery('and', conditions)
    result = yf.screen(q, sortField='pricebookratio.quarterly', sortAsc=True, size=size)
    quotes = result.get('quotes', [])

    stocks = []
    for s in quotes:
        sym = s.get('symbol', '')
        stocks.append({
            "ticker": sym,
            "name": s.get('shortName') or s.get('longName', sym),
            "market": market.upper(),
            "pb": s.get('priceToBook'),
            "pe_ttm": s.get('trailingPE'),
            "dividend_yield": s.get('dividendYield'),
            "market_cap": s.get('marketCap'),
            "current_price": s.get('regularMarketPrice'),
            "roe": s.get('returnOnEquity'),
        })
    return stocks


def broad_universe(market: str = "HK", size: int = 250) -> list[dict]:
    """获取某市场的宽泛标的列表（不施加严格财务条件）。

    用于历史回测等需要先拿 ticker 列表再逐只查历史数据的场景。
    """
    region = MARKET_REGION.get(market.upper(), market.lower())
    q = EquityQuery('and', [
        EquityQuery('eq', ['region', region]),
        EquityQuery('gt', ['pricebookratio.quarterly', 0]),
        EquityQuery('lt', ['pricebookratio.quarterly', 3.0]),
    ])
    result = yf.screen(q, sortField='pricebookratio.quarterly', sortAsc=True, size=size)
    quotes = result.get('quotes', [])

    stocks = []
    for s in quotes:
        sym = s.get('symbol', '')
        stocks.append({
            "ticker": sym,
            "name": s.get('shortName') or s.get('longName', sym),
            "market": market.upper(),
        })
    return stocks


# ---- 兼容旧接口 ----
def get_universe(market: str = "ALL") -> list[dict]:
    """兼容旧代码的接口 -- 内部调用 broad_universe()。

    Args:
        market: "A" / "HK" / "US" / "ALL"
    """
    if market.upper() == "ALL":
        result = []
        for m in ["HK", "A", "US"]:
            result.extend(broad_universe(m))
        return result
    return broad_universe(market.upper())
