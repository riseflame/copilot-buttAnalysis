#!/usr/bin/env python3
"""
港股2021年数据选股 + 回测脚本

1. 基于2021年底的财报/价格数据对港股池做 Tier1 + Tier2 筛选
2. 选出 Top 10 候选
3. 对比2021年底 → 2026年3月的股价表现
"""

from __future__ import annotations

import math
import sys
import os
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

# ── 港股标的池 ────────────────────────────────────────────
HK_SHARES = [
    {"ticker": "0700.HK", "name": "腾讯控股"},
    {"ticker": "9988.HK", "name": "阿里巴巴-SW"},
    {"ticker": "3690.HK", "name": "美团-W"},
    {"ticker": "1398.HK", "name": "工商银行"},
    {"ticker": "3988.HK", "name": "中国银行"},
    {"ticker": "2318.HK", "name": "中国平安"},
    {"ticker": "1522.HK", "name": "招商局中国基金"},
    {"ticker": "0016.HK", "name": "新鸿基地产"},
    {"ticker": "0012.HK", "name": "恒基地产"},
    {"ticker": "0883.HK", "name": "中国海洋石油"},
    {"ticker": "1088.HK", "name": "中国神华"},
    {"ticker": "0002.HK", "name": "中电控股"},
    {"ticker": "2319.HK", "name": "蒙牛乳业"},
    {"ticker": "0291.HK", "name": "华润啤酒"},
    {"ticker": "6862.HK", "name": "海底捞"},
    # 补充更多港股典型烟蒂标的
    {"ticker": "0005.HK", "name": "汇丰控股"},
    {"ticker": "0011.HK", "name": "恒生银行"},
    {"ticker": "0001.HK", "name": "长和"},
    {"ticker": "0003.HK", "name": "香港中华煤气"},
    {"ticker": "0006.HK", "name": "电能实业"},
    {"ticker": "0017.HK", "name": "新世界发展"},
    {"ticker": "0019.HK", "name": "太古股份公司A"},
    {"ticker": "0027.HK", "name": "银河娱乐"},
    {"ticker": "0066.HK", "name": "港铁公司"},
    {"ticker": "0101.HK", "name": "恒隆地产"},
    {"ticker": "0267.HK", "name": "中信股份"},
    {"ticker": "0386.HK", "name": "中国石油化工股份"},
    {"ticker": "0388.HK", "name": "香港交易所"},
    {"ticker": "0688.HK", "name": "中国海外发展"},
    {"ticker": "0857.HK", "name": "中国石油股份"},
    {"ticker": "0939.HK", "name": "建设银行"},
    {"ticker": "0941.HK", "name": "中国移动"},
    {"ticker": "1038.HK", "name": "长江基建集团"},
    {"ticker": "1109.HK", "name": "华润置地"},
    {"ticker": "1113.HK", "name": "长实集团"},
    {"ticker": "1299.HK", "name": "友邦保险"},
    {"ticker": "1928.HK", "name": "金沙中国有限公司"},
    {"ticker": "2007.HK", "name": "碧桂园"},
    {"ticker": "2388.HK", "name": "中银香港"},
    {"ticker": "2628.HK", "name": "中国人寿"},
    {"ticker": "3328.HK", "name": "交通银行"},
    {"ticker": "3968.HK", "name": "招商银行"},
]

# ── Tier 1 港股筛选参数 ─────────────────────────────────
MAX_PB = 1.5
MAX_PE = 50.0
ALLOW_NEGATIVE_PE = True
MIN_DIV_YIELD = 0.015          # 1.5%
MIN_MARKET_CAP_HKD = 5e9       # 50亿 HKD
RISK_FREE_RATE = 3.0           # %

# ── 评分权重 ─────────────────────────────────────────────
W_ROE = 0.20
W_FCF = 0.20
W_R = 0.25
W_EV_EBITDA = 0.15
W_FLOOR = 0.20


def safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def get_price_at_date(ticker_str: str, target_date: str) -> float | None:
    """获取指定日期附近的收盘价。"""
    try:
        stock = yf.Ticker(ticker_str)
        # 取目标日期前后各15天的数据，找最接近的
        end_dt = pd.Timestamp(target_date) + pd.Timedelta(days=15)
        start_dt = pd.Timestamp(target_date) - pd.Timedelta(days=15)
        hist = stock.history(start=start_dt.strftime("%Y-%m-%d"),
                             end=end_dt.strftime("%Y-%m-%d"))
        if hist.empty:
            return None
        # 取最接近目标日期的收盘价
        target = pd.Timestamp(target_date)
        hist.index = hist.index.tz_localize(None)
        idx = hist.index.get_indexer([target], method="nearest")[0]
        return float(hist.iloc[idx]["Close"])
    except Exception:
        return None


def get_2021_financial_data(ticker_str: str) -> dict:
    """提取 2021 财年的财务数据。"""
    result = {}
    stock = yf.Ticker(ticker_str)
    info = stock.info or {}

    # 基本信息
    result["shares"] = safe_float(info.get("sharesOutstanding"))
    result["currency"] = info.get("currency", "HKD")

    # 获取年度财务报表 — 寻找 2021 年数据
    try:
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            # 找到2021年的列(fiscal year ending in 2021)
            cols_2021 = [c for c in bs.columns
                         if hasattr(c, 'year') and c.year == 2021]
            if not cols_2021:
                # 尝试2022年的（某些公司3月结账）
                cols_2021 = [c for c in bs.columns
                             if hasattr(c, 'year') and c.year == 2022
                             and hasattr(c, 'month') and c.month <= 6]
            if cols_2021:
                col = cols_2021[0]
                # 股东权益
                for key in ["Stockholders Equity", "Total Stockholders Equity",
                            "Ordinary Shares Number", "Common Stock Equity"]:
                    if key in bs.index:
                        result["equity"] = safe_float(bs.loc[key, col])
                        break
                # 总资产
                if "Total Assets" in bs.index:
                    result["total_assets"] = safe_float(bs.loc["Total Assets", col])
                # 总负债
                if "Total Debt" in bs.index:
                    result["total_debt"] = safe_float(bs.loc["Total Debt", col])
                elif "Total Liabilities Net Minority Interest" in bs.index:
                    result["total_liabilities"] = safe_float(
                        bs.loc["Total Liabilities Net Minority Interest", col])
                # 现金
                for key in ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]:
                    if key in bs.index:
                        result["cash"] = safe_float(bs.loc[key, col])
                        break
    except Exception as e:
        print(f"    [BS WARN] {e}")

    # 损益表
    try:
        inc = stock.financials
        if inc is not None and not inc.empty:
            cols_2021 = [c for c in inc.columns
                         if hasattr(c, 'year') and c.year == 2021]
            if not cols_2021:
                cols_2021 = [c for c in inc.columns
                             if hasattr(c, 'year') and c.year == 2022
                             and hasattr(c, 'month') and c.month <= 6]
            if cols_2021:
                col = cols_2021[0]
                if "Net Income" in inc.index:
                    result["net_income"] = safe_float(inc.loc["Net Income", col])
                if "Total Revenue" in inc.index:
                    result["revenue"] = safe_float(inc.loc["Total Revenue", col])
                if "Gross Profit" in inc.index:
                    result["gross_profit"] = safe_float(inc.loc["Gross Profit", col])
                if "EBITDA" in inc.index:
                    result["ebitda"] = safe_float(inc.loc["EBITDA", col])
                elif "Normalized EBITDA" in inc.index:
                    result["ebitda"] = safe_float(inc.loc["Normalized EBITDA", col])
    except Exception as e:
        print(f"    [INC WARN] {e}")

    # 现金流量表
    try:
        cf = stock.cashflow
        if cf is not None and not cf.empty:
            cols_2021 = [c for c in cf.columns
                         if hasattr(c, 'year') and c.year == 2021]
            if not cols_2021:
                cols_2021 = [c for c in cf.columns
                             if hasattr(c, 'year') and c.year == 2022
                             and hasattr(c, 'month') and c.month <= 6]
            if cols_2021:
                col = cols_2021[0]
                if "Free Cash Flow" in cf.index:
                    result["fcf"] = safe_float(cf.loc["Free Cash Flow", col])
                if "Operating Cash Flow" in cf.index:
                    result["ocf"] = safe_float(cf.loc["Operating Cash Flow", col])
    except Exception as e:
        print(f"    [CF WARN] {e}")

    # 股息 — 2021年度合计
    try:
        divs = stock.dividends
        if divs is not None and len(divs) > 0:
            divs_2021 = divs[(divs.index.year == 2021) | (divs.index.year == 2022)]
            # 2021年和2022年上半年的分红（2021财年通常在2022上半年派发）
            if len(divs_2021) > 0:
                result["annual_dividend"] = float(divs_2021[divs_2021.index.year == 2021].sum())
                if result["annual_dividend"] == 0:
                    result["annual_dividend"] = float(divs_2021.sum()) / max(len(set(divs_2021.index.year)), 1)
    except Exception:
        pass

    return result


def tier1_screen(stock: dict) -> dict | None:
    """对单只港股做 2021 年数据的 Tier 1 筛选。"""
    ticker = stock["ticker"]
    name = stock["name"]

    print(f"  {ticker} {name}...", end="", flush=True)

    # 获取 2021 年底价格
    price_2021 = get_price_at_date(ticker, "2021-12-31")
    if not price_2021 or price_2021 <= 0:
        print(" [SKIP] 无2021年价格")
        return None

    # 获取 2021 财务数据
    fin = get_2021_financial_data(ticker)
    shares = fin.get("shares")

    if not shares or shares <= 0:
        print(" [SKIP] 无股本数据")
        return None

    # 计算 2021 年底市值
    market_cap = price_2021 * shares

    # 计算 PB
    equity = fin.get("equity")
    bvps = equity / shares if equity and shares else None
    pb = price_2021 / bvps if bvps and bvps > 0 else None

    # 计算 PE
    net_income = fin.get("net_income")
    eps = net_income / shares if net_income and shares else None
    pe = price_2021 / eps if eps and eps != 0 else None

    # 股息率
    annual_div = fin.get("annual_dividend", 0) or 0
    div_yield = annual_div / price_2021 if price_2021 > 0 else 0

    # ── 筛选条件 ──
    # PB
    if pb is not None and (pb > MAX_PB or pb <= 0):
        print(f" ✗ PB={pb:.2f}")
        return None

    # PE
    if pe is not None:
        if pe > 0 and pe > MAX_PE:
            print(f" ✗ PE={pe:.1f}")
            return None
        if pe < 0 and not ALLOW_NEGATIVE_PE:
            print(f" ✗ PE<0")
            return None

    # 股息率
    if div_yield < MIN_DIV_YIELD:
        # 亏损标的不强制股息
        if pe is not None and pe > 0:
            print(f" ✗ 股息率={div_yield*100:.2f}%")
            return None

    # 市值
    if market_cap < MIN_MARKET_CAP_HKD:
        print(f" ✗ 市值={market_cap/1e9:.1f}B < 5B")
        return None

    # PB 为 None 时跳过（无法筛选）
    if pb is None:
        print(" [SKIP] 无PB数据")
        return None

    channel = "observation" if (pe is not None and pe < 0) else "main"

    result = {
        "ticker": ticker,
        "name": name,
        "price_2021": round(price_2021, 2),
        "market_cap_B": round(market_cap / 1e9, 1),
        "pb": round(pb, 2) if pb else None,
        "pe": round(pe, 1) if pe else None,
        "div_yield_pct": round(div_yield * 100, 2),
        "channel": channel,
        # 用于 Tier 2
        "equity": equity,
        "net_income": net_income,
        "revenue": fin.get("revenue"),
        "gross_profit": fin.get("gross_profit"),
        "ebitda": fin.get("ebitda"),
        "fcf": fin.get("fcf"),
        "ocf": fin.get("ocf"),
        "total_debt": fin.get("total_debt"),
        "total_liabilities": fin.get("total_liabilities"),
        "total_assets": fin.get("total_assets"),
        "cash": fin.get("cash"),
        "shares": shares,
        "bvps": round(bvps, 2) if bvps else None,
        "annual_dividend": annual_div,
    }

    pe_str = f"{pe:.1f}" if pe else "?"
    print(f" ✓ PB={pb:.2f} PE={pe_str} Div={div_yield*100:.2f}%")
    return result


def tier2_score(candidates: list[dict]) -> pd.DataFrame:
    """对候选列表做 Tier 2 四因子评分。"""
    df = pd.DataFrame(candidates)
    if df.empty:
        return df

    # ROE (%)
    df["roe"] = df.apply(
        lambda r: (r["net_income"] / r["equity"] * 100)
        if r.get("net_income") and r.get("equity") and r["equity"] > 0
        else None, axis=1)

    # 毛利率 (%)
    df["gross_margin"] = df.apply(
        lambda r: (r["gross_profit"] / r["revenue"] * 100)
        if r.get("gross_profit") and r.get("revenue") and r["revenue"] > 0
        else None, axis=1)

    # FCF 收益率 (%)
    df["fcf_yield"] = df.apply(
        lambda r: (r["fcf"] / (r["price_2021"] * r["shares"]) * 100)
        if r.get("fcf") and r.get("price_2021") and r.get("shares")
        and r["price_2021"] > 0 and r["shares"] > 0
        else None, axis=1)

    # EV/EBITDA
    df["ev_ebitda"] = df.apply(
        lambda r: (
            ((r["price_2021"] * r["shares"]) + (r.get("total_debt") or 0) - (r.get("cash") or 0))
            / r["ebitda"]
        )
        if r.get("ebitda") and r["ebitda"] > 0
        else None, axis=1)

    # 穿透回报率 R%
    def calc_R(r):
        fcf = r.get("fcf") or r.get("ocf")
        if not fcf:
            return None
        div_y = r.get("div_yield_pct", 0) or 0
        m = min(div_y, 100) if div_y > 0 else 30.0  # 分配意愿
        mc = r["price_2021"] * r["shares"] if r.get("price_2021") and r.get("shares") else None
        if not mc or mc <= 0:
            return None
        return fcf * (m / 100) / mc * 100

    df["penetration_R"] = df.apply(calc_R, axis=1)

    # 底价溢价率 (%)
    def calc_floor_premium(r):
        baselines = []
        shares = r.get("shares", 0)
        if not shares or shares <= 0:
            return None
        # BVPS
        if r.get("bvps") and r["bvps"] > 0:
            baselines.append(r["bvps"])
        # 净流动资产
        cash = r.get("cash") or 0
        debt = r.get("total_debt") or 0
        nla = (cash - debt) / shares
        if nla > 0:
            baselines.append(nla)
        # 分红折现
        ann_div = r.get("annual_dividend") or 0
        if ann_div > 0:
            baselines.append(ann_div / (max(RISK_FREE_RATE, 3.0) / 100))
        if not baselines:
            return None
        floor = sum(baselines) / len(baselines)
        if floor <= 0:
            return None
        price = r.get("price_2021")
        if not price:
            return None
        return (price / floor - 1) * 100

    df["floor_premium"] = df.apply(calc_floor_premium, axis=1)

    # ── 百分位排名 & 综合评分 ──
    # 越高越好
    for col in ["roe", "fcf_yield", "penetration_R"]:
        if col in df.columns:
            df[f"{col}_pct"] = df[col].rank(pct=True, na_option="bottom")
    # 越低越好
    for col in ["ev_ebitda", "floor_premium"]:
        if col in df.columns:
            df[f"{col}_pct"] = 1.0 - df[col].rank(pct=True, na_option="top")

    df["composite_score"] = (
        W_ROE * df.get("roe_pct", 0) +
        W_FCF * df.get("fcf_yield_pct", 0) +
        W_R * df.get("penetration_R_pct", 0) +
        W_EV_EBITDA * df.get("ev_ebitda_pct", 0) +
        W_FLOOR * df.get("floor_premium_pct", 0)
    ) * 100

    # R 否决门
    df["veto"] = df["penetration_R"].apply(
        lambda x: "Low-Return" if (x is not None and x < RISK_FREE_RATE) else "")

    df = df.sort_values("composite_score", ascending=False)
    return df


def backtest_prices(top10: pd.DataFrame) -> pd.DataFrame:
    """获取当前价格并计算涨跌幅。"""
    results = []
    for _, row in top10.iterrows():
        ticker = row["ticker"]
        print(f"  回测 {ticker} {row['name']}...", end="", flush=True)
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            current_price = safe_float(info.get("currentPrice")) or safe_float(info.get("regularMarketPrice"))
            if current_price and row["price_2021"]:
                change_pct = (current_price / row["price_2021"] - 1) * 100
                print(f" {row['price_2021']:.2f} → {current_price:.2f} ({change_pct:+.1f}%)")
            else:
                change_pct = None
                print(" [无当前价格]")
            results.append({
                "ticker": ticker,
                "name": row["name"],
                "price_2021": row["price_2021"],
                "current_price": current_price,
                "change_pct": round(change_pct, 1) if change_pct is not None else None,
            })
        except Exception as e:
            print(f" ERROR: {e}")
            results.append({
                "ticker": ticker,
                "name": row["name"],
                "price_2021": row["price_2021"],
                "current_price": None,
                "change_pct": None,
            })
        time.sleep(0.5)
    return pd.DataFrame(results)


def main():
    print("=" * 60)
    print("港股 2021 年数据选股 + 回测")
    print("=" * 60)

    # ── Level 1: Tier 1 批量宽筛 ──
    print(f"\n{'='*60}")
    print(f"Level 1: Tier 1 批量宽筛 (2021年数据)")
    print(f"股票池: {len(HK_SHARES)} 只港股")
    print(f"{'='*60}")

    candidates = []
    for stock in HK_SHARES:
        result = tier1_screen(stock)
        if result is not None:
            candidates.append(result)
        time.sleep(0.8)

    print(f"\n📊 Level 1 完成: 通过筛选 {len(candidates)} / {len(HK_SHARES)} 只")

    if not candidates:
        print("无候选标的通过筛选，结束。")
        return

    # 保存 Tier 1
    t1_df = pd.DataFrame(candidates)
    os.makedirs("output/screener", exist_ok=True)
    t1_df.to_csv("output/screener/backtest_tier1_2021.csv", index=False, encoding="utf-8-sig")
    print(f"→ output/screener/backtest_tier1_2021.csv")

    # ── Level 2: 四因子评分 ──
    print(f"\n{'='*60}")
    print(f"Level 2: 四因子评分 & Top 10")
    print(f"{'='*60}")

    scored_df = tier2_score(candidates)

    # 输出 Top 10
    top10 = scored_df.head(10).copy()
    print(f"\n📈 Top 10 候选:")
    print(f"{'排名':>4} {'代码':>10} {'名称':>12} {'评分':>6} {'PB':>6} "
          f"{'PE':>7} {'股息率%':>7} {'ROE%':>7} {'底价溢价%':>9}")
    print("-" * 85)
    for i, (_, r) in enumerate(top10.iterrows()):
        score = f"{r['composite_score']:.1f}" if pd.notna(r.get('composite_score')) else "N/A"
        pb = f"{r['pb']:.2f}" if pd.notna(r.get('pb')) else "?"
        pe = f"{r['pe']:.1f}" if pd.notna(r.get('pe')) else "?"
        div_y = f"{r['div_yield_pct']:.2f}" if pd.notna(r.get('div_yield_pct')) else "?"
        roe = f"{r['roe']:.1f}" if pd.notna(r.get('roe')) else "?"
        fp = f"{r['floor_premium']:.1f}" if pd.notna(r.get('floor_premium')) else "?"
        veto = f" [{r['veto']}]" if r.get('veto') else ""
        print(f"  {i+1:>2}. {r['ticker']:>10} {r['name']:>12} "
              f"{score:>6} {pb:>6} {pe:>7} {div_y:>7} {roe:>7} {fp:>9}{veto}")

    # 保存 Tier 2
    out_cols = ["ticker", "name", "channel", "price_2021", "market_cap_B",
                "pb", "pe", "div_yield_pct", "roe", "gross_margin",
                "fcf_yield", "ev_ebitda", "penetration_R", "floor_premium",
                "composite_score", "veto"]
    available = [c for c in out_cols if c in scored_df.columns]
    scored_df[available].to_csv("output/screener/backtest_tier2_2021.csv",
                                index=False, encoding="utf-8-sig")
    print(f"\n→ output/screener/backtest_tier2_2021.csv")

    # ── 回测：对比 2021 → 2026 ──
    print(f"\n{'='*60}")
    print(f"回测: 2021年底 → 2026年3月 股价变动")
    print(f"{'='*60}")

    bt_df = backtest_prices(top10)

    print(f"\n📊 回测结果:")
    print(f"{'排名':>4} {'代码':>10} {'名称':>12} {'2021价格':>10} {'当前价格':>10} {'涨跌幅':>10}")
    print("-" * 65)
    for i, (_, r) in enumerate(bt_df.iterrows()):
        p21 = f"{r['price_2021']:.2f}" if pd.notna(r.get('price_2021')) else "?"
        p_now = f"{r['current_price']:.2f}" if pd.notna(r.get('current_price')) else "?"
        chg = f"{r['change_pct']:+.1f}%" if pd.notna(r.get('change_pct')) else "N/A"
        print(f"  {i+1:>2}. {r['ticker']:>10} {r['name']:>12} {p21:>10} {p_now:>10} {chg:>10}")

    # 统计
    valid = bt_df.dropna(subset=["change_pct"])
    if not valid.empty:
        avg_return = valid["change_pct"].mean()
        median_return = valid["change_pct"].median()
        best = valid.loc[valid["change_pct"].idxmax()]
        worst = valid.loc[valid["change_pct"].idxmin()]
        winners = len(valid[valid["change_pct"] > 0])
        losers = len(valid[valid["change_pct"] <= 0])

        print(f"\n📈 汇总统计:")
        print(f"  平均收益: {avg_return:+.1f}%")
        print(f"  中位收益: {median_return:+.1f}%")
        print(f"  最佳表现: {best['name']} ({best['change_pct']:+.1f}%)")
        print(f"  最差表现: {worst['name']} ({worst['change_pct']:+.1f}%)")
        print(f"  上涨/下跌: {winners}/{losers}")

    # 合并保存最终报告数据
    final = top10[["ticker", "name", "pb", "pe", "div_yield_pct",
                    "composite_score", "price_2021"]].copy()
    final = final.merge(bt_df[["ticker", "current_price", "change_pct"]],
                        on="ticker", how="left")
    final.to_csv("output/screener/backtest_result_2021_hk.csv",
                 index=False, encoding="utf-8-sig")
    print(f"\n→ output/screener/backtest_result_2021_hk.csv")


if __name__ == "__main__":
    main()
