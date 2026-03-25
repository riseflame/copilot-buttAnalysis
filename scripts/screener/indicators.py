"""
指标计算引擎 — 穿透回报率、底价、EV/EBITDA、FCF 收益率等

所有计算使用 yfinance 返回的原始数据，字段名遵循 yfinance Ticker.info 和
Ticker.financials / balance_sheet / cashflow 的命名。
"""

from __future__ import annotations

import math
from typing import Any

import yfinance as yf
import pandas as pd


def safe_float(val: Any) -> float | None:
    """安全转换为 float，NaN/None 返回 None。"""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


# ── 基础信息提取 ─────────────────────────────────────────

def fetch_stock_info(ticker: str) -> dict:
    """从 yfinance 获取单只股票的核心指标。
    
    Returns:
        dict with keys: ticker, name, market_cap, pe, pb, dividend_yield,
        current_price, currency, shares_outstanding, roe, gross_margin,
        debt_to_equity, ebitda, total_debt, total_cash, ...
    """
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    return {
        "ticker": ticker,
        "name": info.get("shortName") or info.get("longName", ticker),
        "current_price": safe_float(info.get("currentPrice"))
                         or safe_float(info.get("regularMarketPrice")),
        "market_cap": safe_float(info.get("marketCap")),
        "pe_ttm": safe_float(info.get("trailingPE")),
        "pb": safe_float(info.get("priceToBook")),
        "dividend_yield": safe_float(info.get("dividendYield")),  # 0.03 = 3%
        "shares_outstanding": safe_float(info.get("sharesOutstanding")),
        "currency": info.get("currency", ""),

        # 财务质量
        "roe": safe_float(info.get("returnOnEquity")),            # 0.12 = 12%
        "gross_margin": safe_float(info.get("grossMargins")),     # 0.30 = 30%
        "debt_to_equity": safe_float(info.get("debtToEquity")),   # 百分比

        # 估值相关
        "ebitda": safe_float(info.get("ebitda")),
        "total_debt": safe_float(info.get("totalDebt")),
        "total_cash": safe_float(info.get("totalCash")),
        "enterprise_value": safe_float(info.get("enterpriseValue")),
        "ev_to_ebitda": safe_float(info.get("enterpriseToEbitda")),
        "free_cashflow": safe_float(info.get("freeCashflow")),
        "operating_cashflow": safe_float(info.get("operatingCashflow")),
        "total_revenue": safe_float(info.get("totalRevenue")),
        "net_income": safe_float(info.get("netIncomeToCommon")),
        "book_value": safe_float(info.get("bookValue")),          # 每股净资产
    }


# ── Tier 2 指标计算 ──────────────────────────────────────

def calc_fcf_yield(info: dict) -> float | None:
    """FCF 收益率 = Free Cash Flow / Market Cap × 100%。"""
    fcf = info.get("free_cashflow")
    mc = info.get("market_cap")
    if fcf is None or mc is None or mc <= 0:
        return None
    return fcf / mc * 100


def calc_ev_ebitda(info: dict) -> float | None:
    """EV/EBITDA，优先使用 yfinance 直接字段。"""
    direct = info.get("ev_to_ebitda")
    if direct is not None:
        return direct
    ev = info.get("enterprise_value")
    ebitda = info.get("ebitda")
    if ev is None or ebitda is None or ebitda == 0:
        return None
    return ev / ebitda


def calc_penetration_rate(info: dict, dividend_tax: float = 0.0,
                          risk_free_rate: float = 3.0) -> dict:
    """穿透回报率粗算。

    简化公式：R% = AA × M / 市值
    AA ≈ OCF - |Capex|
    M = 分配意愿 (用 dividend_yield 近似)

    Returns:
        dict with AA, M, R, R_vs_Rf (pass/fail)
    """
    result: dict = {}
    ocf = info.get("operating_cashflow")
    fcf = info.get("free_cashflow")
    mc = info.get("market_cap")
    div_yield = info.get("dividend_yield")

    if ocf is not None and fcf is not None:
        # AA ≈ FCF (已扣 capex)
        aa = fcf
    elif ocf is not None:
        aa = ocf
    else:
        return {"R": None, "R_vs_Rf": None}

    result["AA"] = aa

    # M: 分配意愿（近似用股息率 × 市值 / 净利润）
    # 简化：直接用 dividend_yield 作为 M% 的代理
    if div_yield is not None and div_yield > 0:
        m = min(div_yield * 100 * (1 - dividend_tax), 100)
    else:
        m = 30.0  # 无分红时默认 30% 分配假设

    result["M"] = m

    if mc is not None and mc > 0:
        r = aa * (m / 100) / mc * 100  # 百分比
        result["R"] = r
        result["R_vs_Rf"] = "pass" if r >= risk_free_rate else "fail"
    else:
        result["R"] = None
        result["R_vs_Rf"] = None

    return result


def calc_floor_prices(ticker: str, info: dict,
                      risk_free_rate: float = 3.0) -> dict:
    """底价计算（5 种方法取算术平均）。

    1. 净流动资产/股 = (Cash + TradableAssets - InterestBearingDebt) / Shares
    2. BVPS = BookValue per share (直接取)
    3. 10 年历史最低价
    4. 分红折现价 = 近 3 年平均每股分红 / max(Rf, 3%)
    5. 悲观 FCF 资本化价 = 近年最小 FCF / Rf% / Shares
    """
    result: dict = {}
    shares = info.get("shares_outstanding")
    current_price = info.get("current_price")

    if not shares or shares <= 0:
        return {"composite_floor": None, "premium": None}

    baselines: list[tuple[str, float]] = []

    # ① 净流动资产/股
    cash = info.get("total_cash") or 0
    debt = info.get("total_debt") or 0
    nla = (cash - debt) / shares
    if nla != 0:
        baselines.append(("net_liquid_assets", nla))
        result["net_liquid_assets"] = nla

    # ② BVPS
    bvps = info.get("book_value")
    if bvps is not None:
        baselines.append(("bvps", bvps))
        result["bvps"] = bvps

    # ③ 10 年历史最低价
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="10y", interval="1mo")
        if not hist.empty:
            min_close = hist["Close"].dropna().min()
            if min_close is not None and not math.isnan(min_close):
                baselines.append(("10yr_low", float(min_close)))
                result["10yr_low"] = float(min_close)
    except Exception:
        pass

    # ④ 分红折现价
    try:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        if dividends is not None and len(dividends) > 0:
            # 近 3 年
            cutoff = pd.Timestamp.now(tz=dividends.index.tz) - pd.DateOffset(years=3)
            recent = dividends[dividends.index >= cutoff]
            if len(recent) > 0:
                # 年均分红
                years = max((recent.index[-1] - recent.index[0]).days / 365, 1)
                annual_div = recent.sum() / years
                discount = max(risk_free_rate, 3.0) / 100
                div_implied = annual_div / discount
                if div_implied > 0:
                    baselines.append(("dividend_implied", div_implied))
                    result["dividend_implied"] = div_implied
    except Exception:
        pass

    # ⑤ 悲观 FCF 资本化价
    fcf = info.get("free_cashflow")
    if fcf is not None and fcf > 0 and risk_free_rate > 0:
        pessimistic_fcf = fcf * 0.7  # 打 7 折
        fcf_cap = pessimistic_fcf / (risk_free_rate / 100) / shares
        if fcf_cap > 0:
            baselines.append(("pessimistic_fcf", fcf_cap))
            result["pessimistic_fcf"] = fcf_cap

    # 综合底价
    if baselines:
        valid = [v for _, v in baselines if v > 0]
        if valid:
            result["composite_floor"] = sum(valid) / len(valid)
        else:
            result["composite_floor"] = None
    else:
        result["composite_floor"] = None

    # 溢价率
    floor = result.get("composite_floor")
    if floor and floor > 0 and current_price and current_price > 0:
        result["premium"] = (current_price / floor - 1) * 100
    else:
        result["premium"] = None

    return result
