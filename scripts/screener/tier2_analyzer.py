#!/usr/bin/env python3
"""
Tier 2 四因子深度评分 — 对 Tier 1 候选逐只计算评分并排名

评分公式（参考龟龟投资策略）：
  综合评分 = ROE(20%) + FCF收益率(20%) + 穿透率R(25%)
           + EV/EBITDA逆序(15%) + 底价溢价逆序(20%)

用法:
    python scripts/screener/tier2_analyzer.py --input output/screener/tier1_candidates.csv
    python scripts/screener/tier2_analyzer.py --input tier1.csv --top 30
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from indicators import (
    calc_ev_ebitda,
    calc_fcf_yield,
    calc_floor_prices,
    calc_penetration_rate,
    fetch_stock_info,
)
from screener_config import ScreenerConfig, get_params


def analyze_single_stock(row: pd.Series, config: ScreenerConfig) -> dict | None:
    """对单只股票执行 Tier 2 全量分析。"""
    ticker = row["ticker"]
    market = row.get("market", "A")
    params = get_params(market)

    # 重新获取最新数据（Tier 1 可能是缓存的）
    try:
        info = fetch_stock_info(ticker)
    except Exception as e:
        print(f" ERROR({e})")
        return None

    # yfinance dividendYield: 通常为小数（0.03=3%），但部分标的可能返回百分比值
    raw_div = info.get("dividend_yield") or 0
    div_pct = raw_div * 100 if raw_div < 1 else raw_div  # 归一化为百分比

    result = {
        "ticker": ticker,
        "name": row.get("stock_name", info.get("name", "")),
        "market": market,
        "channel": row.get("channel", "main"),
        "current_price": info.get("current_price"),
        "pb": info.get("pb"),
        "pe_ttm": info.get("pe_ttm"),
        "dividend_yield": div_pct,
        "market_cap": info.get("market_cap"),
        "currency": info.get("currency", ""),
    }

    # ── 财务质量检查（ROE / 毛利率 / 负债率）──
    roe_raw = info.get("roe")  # 0.12 = 12%
    roe_pct = roe_raw * 100 if roe_raw is not None else None
    result["roe"] = roe_pct

    gm_raw = info.get("gross_margin")  # 0.30 = 30%
    gm_pct = gm_raw * 100 if gm_raw is not None else None
    result["gross_margin"] = gm_pct

    dte = info.get("debt_to_equity")  # 已是百分比
    result["debt_to_equity"] = dte

    # 判断是否为金融行业（银行/保险/券商没有传统毛利率）
    name = result.get("name", "")
    is_financial = any(kw in name for kw in ["银行", "Bank", "保险", "Insurance",
                                              "证券", "Securities", "金融", "Financial"])

    # 财务质量否决（主通道）
    if result["channel"] == "main":
        if roe_pct is not None and roe_pct < params.min_roe:
            result["veto_reason"] = f"ROE={roe_pct:.1f}% < {params.min_roe}%"
            return result  # 保留但标记否决
        if not is_financial and gm_pct is not None and gm_pct < params.min_gross_margin:
            result["veto_reason"] = f"毛利率={gm_pct:.1f}% < {params.min_gross_margin}%"
            return result

    # ── 四因子指标 ──

    # 因子 1: FCF 收益率
    fcf_yield = calc_fcf_yield(info)
    result["fcf_yield"] = fcf_yield

    # 因子 2: EV/EBITDA
    ev_ebitda = calc_ev_ebitda(info)
    result["ev_ebitda"] = ev_ebitda

    # 因子 3: 穿透回报率
    pen = calc_penetration_rate(
        info,
        dividend_tax=params.dividend_tax_rate,
        risk_free_rate=params.risk_free_rate
    )
    result["penetration_R"] = pen.get("R")
    result["R_vs_Rf"] = pen.get("R_vs_Rf")
    result["AA"] = pen.get("AA")

    # 因子 4: 底价 & 溢价
    floor = calc_floor_prices(ticker, info, params.risk_free_rate)
    result["composite_floor"] = floor.get("composite_floor")
    result["floor_premium"] = floor.get("premium")
    result["bvps"] = floor.get("bvps")
    result["10yr_low"] = floor.get("10yr_low")

    return result


def compute_rankings(df: pd.DataFrame, config: ScreenerConfig) -> pd.DataFrame:
    """计算百分位排名和综合评分。"""
    if df.empty:
        return df
    df = df.copy()

    # 排除已否决的
    veto_col = df["veto_reason"] if "veto_reason" in df.columns else pd.Series("", index=df.index)
    has_veto = veto_col.notna() & (veto_col != "")
    scored = df[~has_veto].copy()
    vetoed = df[has_veto].copy()

    if scored.empty:
        df["composite_score"] = None
        return df

    # 越高越好的指标 → rank(pct=True)
    for col in ["roe", "fcf_yield", "penetration_R"]:
        if col in scored.columns:
            scored[f"{col}_pctile"] = scored[col].rank(
                pct=True, na_option="bottom")
        else:
            scored[f"{col}_pctile"] = 0.0

    # 越低越好的指标 → 1 - rank(pct=True)
    for col in ["ev_ebitda", "floor_premium"]:
        if col in scored.columns:
            scored[f"{col}_pctile"] = 1.0 - scored[col].rank(
                pct=True, na_option="top")
        else:
            scored[f"{col}_pctile"] = 0.0

    # 综合评分
    scored["composite_score"] = (
        config.weight_roe * scored.get("roe_pctile", 0) +
        config.weight_fcf_yield * scored.get("fcf_yield_pctile", 0) +
        config.weight_penetration_r * scored.get("penetration_R_pctile", 0) +
        config.weight_ev_ebitda * scored.get("ev_ebitda_pctile", 0) +
        config.weight_floor_premium * scored.get("floor_premium_pctile", 0)
    ) * 100  # 缩放到 0-100

    scored = scored.sort_values("composite_score", ascending=False)

    # 合并否决的
    if not vetoed.empty:
        vetoed["composite_score"] = None
        # 对齐列以避免 FutureWarning
        shared_cols = scored.columns.union(vetoed.columns)
        result = pd.concat([scored.reindex(columns=shared_cols),
                            vetoed.reindex(columns=shared_cols)], ignore_index=True)
    else:
        result = scored

    return result


def run_tier2(input_path: str, output_path: str | None = None,
              top_n: int = 20, config: ScreenerConfig | None = None) -> pd.DataFrame:
    """执行 Tier 2 四因子评分。"""
    config = config or ScreenerConfig()

    df = pd.read_csv(input_path)
    total = len(df)
    print(f"=== Tier 2 四因子评分 ===")
    print(f"  输入: {total} 只候选")

    results = []
    for i, (_, row) in enumerate(df.iterrows()):
        ticker = row["ticker"]
        name = row.get("stock_name", "")
        print(f"  [{i+1}/{total}] {ticker} {name}...", end="", flush=True)

        stock_result = analyze_single_stock(row, config)
        if stock_result is not None:
            results.append(stock_result)
            veto = stock_result.get("veto_reason", "")
            if veto:
                print(f" VETO({veto})")
            else:
                score_r = stock_result.get("penetration_R")
                r_str = f"R={score_r:.1f}%" if score_r is not None else "R=?"
                print(f" OK {r_str}")
        else:
            print(" SKIP")
        time.sleep(config.request_delay)

    result_df = pd.DataFrame(results)

    if not result_df.empty:
        result_df = compute_rankings(result_df, config)

    # 统计
    if not result_df.empty and "veto_reason" in result_df.columns:
        veto_col = result_df["veto_reason"]
        passed = len(result_df[veto_col.isna() | (veto_col == "")])
    elif not result_df.empty:
        passed = len(result_df)
    else:
        passed = 0
    vetoed = total - passed
    print(f"\n  分析: {len(result_df)} 只 | 通过: {passed} 只 | 否决: {vetoed} 只")

    # Top N
    if not result_df.empty:
        top = result_df.head(top_n)
        print(f"\n  === Top {min(top_n, len(top))} ===")
        for i, (_, r) in enumerate(top.iterrows()):
            score = r.get("composite_score")
            score_str = f"{score:.1f}" if score is not None else "N/A"
            pb = r.get("pb")
            pb_str = f"{pb:.2f}" if pb is not None else "?"
            roe = r.get("roe")
            roe_str = f"{roe:.1f}%" if roe is not None else "?"
            div_y = r.get("dividend_yield", 0)
            div_str = f"{div_y:.1f}%" if div_y else "0%"
            print(f"  {i+1:>3}. {r.get('ticker','?'):>10} {r.get('name',''):>10} "
                  f"| 评分 {score_str:>5} | PB {pb_str:>5} "
                  f"| ROE {roe_str:>6} | 股息 {div_str:>5}")

    # 保存
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        # 选择输出列
        out_cols = [
            "ticker", "name", "market", "channel",
            "current_price", "pb", "pe_ttm", "dividend_yield",
            "roe", "gross_margin", "debt_to_equity",
            "fcf_yield", "ev_ebitda", "penetration_R", "R_vs_Rf",
            "composite_floor", "floor_premium",
            "composite_score", "veto_reason",
        ]
        available = [c for c in out_cols if c in result_df.columns]
        result_df[available].to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"\n  输出: {output_path}")

    return result_df


def main():
    parser = argparse.ArgumentParser(description="Tier 2 四因子评分")
    parser.add_argument("--input", required=True,
                        help="Tier 1 候选 CSV 路径")
    parser.add_argument("--output", default=None,
                        help="输出 CSV 路径")
    parser.add_argument("--top", type=int, default=20,
                        help="输出 Top N (默认 20)")
    args = parser.parse_args()

    if args.output is None:
        date_str = datetime.now().strftime("%Y%m%d")
        args.output = f"output/screener/tier2_ranked_{date_str}.csv"

    run_tier2(input_path=args.input, output_path=args.output, top_n=args.top)


if __name__ == "__main__":
    main()
