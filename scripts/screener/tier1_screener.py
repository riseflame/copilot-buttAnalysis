#!/usr/bin/env python3
"""
Tier 1 批量宽筛 — 从全市场数据中筛选烟蒂股候选

两种模式：
  1. 实时模式（默认）：调用 yf.screen() 直接从全市场数据中按条件筛选
  2. 历史模式（--year）：先获取 ticker 列表，再逐只拉历史数据过滤

用法:
    python scripts/screener/tier1_screener.py --market HK
    python scripts/screener/tier1_screener.py --market HK --year 2022
    python scripts/screener/tier1_screener.py --market A --output output/screener/tier1.csv
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screener_config import ScreenerConfig, get_params
from stock_universe import screen_universe, broad_universe


def run_tier1_realtime(market: str = "HK", output_path: str | None = None,
                       config: ScreenerConfig | None = None) -> pd.DataFrame:
    """实时模式：直接用 yf.screen() API 从全市场筛选。

    一次 API 请求即可获取最多 250 只符合条件的标的，无需逐只查询。
    """
    config = config or ScreenerConfig()
    params = get_params(market)

    print(f"=== Tier 1 批量宽筛（实时模式）===")
    print(f"  市场: {market}")
    print(f"  条件: PB<{params.max_pb}, PE<{params.max_pe},"
          f" 股息率>{params.min_dividend_yield*100:.1f}%")

    # 直接从全市场筛选
    candidates = screen_universe(
        market=market,
        max_pb=params.max_pb,
        max_pe=params.max_pe,
        min_div_yield=params.min_dividend_yield * 100 if params.require_dividend else 0,
        size=250,
    )

    print(f"  Yahoo Finance screener 返回: {len(candidates)} 只")

    if not candidates:
        print("  [WARN] 未找到符合条件的标的")
        return pd.DataFrame()

    df = pd.DataFrame(candidates)

    # 归一化 dividend_yield 为百分比
    if 'dividend_yield' in df.columns:
        df['dividend_yield_pct'] = df['dividend_yield'].apply(
            lambda x: x * 100 if x is not None and x < 1 else (x if x is not None else 0)
        )

    # 通道分流
    df['channel'] = 'main'
    if 'pb' in df.columns:
        df.loc[df['pb'] >= 1.0, 'channel'] = 'observation'
    if 'pe_ttm' in df.columns:
        df.loc[df['pe_ttm'].isna() | (df['pe_ttm'] < 0), 'channel'] = 'observation'

    # 市值过滤
    if 'market_cap' in df.columns and params.min_market_cap > 0:
        before = len(df)
        df = df[df['market_cap'].isna() | (df['market_cap'] >= params.min_market_cap)]
        filtered = before - len(df)
        if filtered > 0:
            print(f"  市值过滤: 移除 {filtered} 只（< {params.min_market_cap/1e9:.1f}B）")

    # 标准化列名
    df = df.rename(columns={'name': 'stock_name'})
    df = df.sort_values('pb', ascending=True, na_position='last')

    main_count = len(df[df['channel'] == 'main'])
    obs_count = len(df[df['channel'] == 'observation'])
    print(f"\n  通过筛选: {len(df)} 只（主通道: {main_count}, 观察通道: {obs_count}）")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"  输出: {output_path}")

    return df


def _get_historical_data(ticker: str, year: int) -> dict | None:
    """获取指定年份的历史财务数据。"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # 获取年底价格
        end_date = f"{year+1}-01-15"
        start_date = f"{year}-11-01"
        hist = stock.history(start=start_date, end=end_date)
        if hist.empty:
            return None
        price = float(hist['Close'].iloc[-1])

        # 获取历史财务数据
        bs = stock.balance_sheet
        fin = stock.financials
        cf = stock.cashflow

        # 找到匹配年份的列
        def find_year_col(df, target_year):
            if df is None or df.empty:
                return None
            for col in df.columns:
                if hasattr(col, 'year') and col.year == target_year:
                    return col
            return None

        bs_col = find_year_col(bs, year)
        fin_col = find_year_col(fin, year)
        cf_col = find_year_col(cf, year)

        # 计算 PB
        pb = None
        if bs_col is not None:
            equity = bs.at['Stockholders Equity', bs_col] if 'Stockholders Equity' in bs.index else \
                     bs.at['Total Stockholder Equity', bs_col] if 'Total Stockholder Equity' in bs.index else None
            shares = info.get('sharesOutstanding')
            if equity and shares and shares > 0:
                bvps = equity / shares
                if bvps > 0:
                    pb = price / bvps

        # 计算 PE
        pe = None
        if fin_col is not None:
            ni = fin.at['Net Income', fin_col] if 'Net Income' in fin.index else None
            shares = info.get('sharesOutstanding')
            if ni and shares and shares > 0 and ni > 0:
                eps = ni / shares
                pe = price / eps

        # 股息率
        div_yield = None
        try:
            divs = stock.dividends
            if divs is not None and len(divs) > 0:
                year_divs = divs[(divs.index.year == year)]
                if len(year_divs) > 0:
                    annual_div = year_divs.sum()
                    if price > 0:
                        div_yield = annual_div / price
        except Exception:
            pass

        # ROE
        roe = None
        if fin_col is not None and bs_col is not None:
            ni = fin.at['Net Income', fin_col] if 'Net Income' in fin.index else None
            equity = bs.at['Stockholders Equity', bs_col] if 'Stockholders Equity' in bs.index else None
            if ni and equity and equity > 0:
                roe = ni / equity

        return {
            "ticker": ticker,
            "name": info.get('shortName') or info.get('longName', ticker),
            "current_price": price,
            "pb": pb,
            "pe_ttm": pe,
            "dividend_yield": div_yield,
            "roe": roe,
            "market_cap": info.get('marketCap'),
        }
    except Exception:
        return None


def run_tier1_historical(market: str = "HK", year: int = 2022,
                         output_path: str | None = None,
                         config: ScreenerConfig | None = None) -> pd.DataFrame:
    """历史模式：先获取 ticker 列表，再逐只用历史数据筛选。"""
    config = config or ScreenerConfig()
    params = get_params(market)

    print(f"=== Tier 1 批量宽筛（历史模式：{year}年）===")

    # 先从全市场拿到 ticker 列表（用当前宽松 PB<3 筛选获取候选池）
    print(f"  从全市场获取 ticker 列表...")
    universe = broad_universe(market, size=250)
    print(f"  候选池: {len(universe)} 只")

    candidates = []
    for i, stock in enumerate(universe):
        ticker = stock['ticker']
        name = stock.get('name', ticker)
        print(f"  [{i+1}/{len(universe)}] {ticker} {name}...", end="", flush=True)

        data = _get_historical_data(ticker, year)
        if data is None:
            print(" ✗ 数据不足")
            continue

        pb = data.get('pb')
        pe = data.get('pe_ttm')
        div_y = data.get('dividend_yield') or 0

        # PB 筛选
        if pb is None or pb <= 0 or pb > params.max_pb:
            print(f" ✗ PB={pb}")
            continue

        # PE 筛选
        if pe is not None and pe > 0 and pe > params.max_pe:
            print(f" ✗ PE={pe:.1f}")
            continue

        # 股息率筛选
        if params.require_dividend and div_y < params.min_dividend_yield:
            # 允许观察通道
            data['channel'] = 'observation'
        else:
            data['channel'] = 'main' if (pb < 1.0) else 'observation'

        data['market'] = market
        candidates.append(data)
        pb_str = f"{pb:.2f}" if pb else "?"
        print(f" ✓ PB={pb_str}")

        time.sleep(config.request_delay)

    df = pd.DataFrame(candidates)
    if not df.empty:
        df = df.rename(columns={'name': 'stock_name'})
        if 'dividend_yield' in df.columns:
            df['dividend_yield_pct'] = df['dividend_yield'].apply(
                lambda x: x * 100 if x is not None and x < 1 else (x if x is not None else 0)
            )
        df = df.sort_values('pb', ascending=True, na_position='last')

    main_count = len(df[df['channel'] == 'main']) if not df.empty else 0
    obs_count = len(df[df['channel'] == 'observation']) if not df.empty else 0
    print(f"\n  通过筛选: {len(df)} 只（主通道: {main_count}, 观察通道: {obs_count}）")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"  输出: {output_path}")

    return df


def run_tier1(market: str = "ALL", output_path: str | None = None,
              config: ScreenerConfig | None = None, year: int | None = None) -> pd.DataFrame:
    """统一入口：根据是否指定 year 选择实时/历史模式。"""
    if year:
        return run_tier1_historical(market, year, output_path, config)
    else:
        return run_tier1_realtime(market, output_path, config)


def main():
    parser = argparse.ArgumentParser(description="Tier 1 批量宽筛")
    parser.add_argument("--market", default="HK",
                        choices=["A", "HK", "US", "ALL"],
                        help="目标市场（默认 HK）")
    parser.add_argument("--year", type=int, default=None,
                        help="历史数据年份（如 2022），默认使用实时数据")
    parser.add_argument("--output", default=None,
                        help="输出 CSV 路径")
    args = parser.parse_args()

    if args.output is None:
        date_str = datetime.now().strftime("%Y%m%d")
        suffix = f"_{args.year}" if args.year else f"_{date_str}"
        args.output = f"output/screener/tier1_candidates{suffix}.csv"

    run_tier1(market=args.market, output_path=args.output, year=args.year)


if __name__ == "__main__":
    main()
