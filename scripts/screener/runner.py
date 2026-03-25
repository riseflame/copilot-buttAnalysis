#!/usr/bin/env python3
"""
选股器统一入口 — 一键执行 Tier 1 + Tier 2 完整流程

用法:
    # 全市场选股
    python scripts/screener/runner.py

    # 仅 A 股
    python scripts/screener/runner.py --market A

    # 仅 Tier 1
    python scripts/screener/runner.py --tier1-only

    # 自定义 Top N
    python scripts/screener/runner.py --top 30

    # 指定输出目录
    python scripts/screener/runner.py --output-dir output/screener
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screener_config import ScreenerConfig
from tier1_screener import run_tier1
from tier2_analyzer import run_tier2


def run_pipeline(market: str = "ALL", tier1_only: bool = False,
                 top_n: int = 20, output_dir: str = "output/screener"):
    """执行 Tier 1 → Tier 2 完整流水线。"""
    config = ScreenerConfig(top_n=top_n, output_dir=output_dir)
    date_str = datetime.now().strftime("%Y%m%d")

    os.makedirs(output_dir, exist_ok=True)
    tier1_path = os.path.join(output_dir, f"tier1_candidates_{date_str}.csv")
    tier2_path = os.path.join(output_dir, f"tier2_ranked_{date_str}.csv")

    # ── Tier 1 ──
    print("=" * 60)
    tier1_df = run_tier1(market=market, output_path=tier1_path, config=config)

    if tier1_df.empty:
        print("\n⚠ Tier 1 筛选结果为空，请检查股票池或放宽条件。")
        return

    if tier1_only:
        print(f"\n✅ Tier 1 完成，{len(tier1_df)} 只候选已保存到 {tier1_path}")
        return

    # ── Tier 2 ──
    print("\n" + "=" * 60)
    tier2_df = run_tier2(input_path=tier1_path, output_path=tier2_path,
                         top_n=top_n, config=config)

    # ── 汇总 ──
    print("\n" + "=" * 60)
    print("✅ 选股流程完成")
    print(f"  Tier 1 候选: {tier1_path}")
    print(f"  Tier 2 排名: {tier2_path}")
    print(f"  共 {len(tier2_df)} 只通过评分")

    # 生成简要 Markdown 报告
    report_path = os.path.join(output_dir, f"screening_report_{date_str}.md")
    _generate_report(tier1_df, tier2_df, report_path, market, date_str, top_n)
    print(f"  报告: {report_path}")


def _generate_report(tier1_df, tier2_df, path: str,
                     market: str, date_str: str, top_n: int):
    """生成 Markdown 选股报告。"""
    lines = [
        f"# 选股报告 {date_str}",
        "",
        f"**市场**: {market} | **日期**: {date_str} | **Top N**: {top_n}",
        "",
        "## Tier 1 批量宽筛",
        "",
        f"- 股票池: {len(tier1_df) + 0} 只通过",
    ]

    if not tier1_df.empty and "market" in tier1_df.columns:
        for m in ["A", "HK", "US"]:
            cnt = len(tier1_df[tier1_df["market"] == m])
            if cnt > 0:
                lines.append(f"  - {m}: {cnt} 只")

    lines += ["", "## Tier 2 四因子评分", ""]

    if not tier2_df.empty and "composite_score" in tier2_df.columns:
        scored = tier2_df[tier2_df["composite_score"].notna()].head(top_n)
        lines.append("| # | 代码 | 名称 | 市场 | PB | ROE | 股息率 | "
                      "FCF收益率 | R% | EV/EBITDA | 底价溢价 | 评分 |")
        lines.append("|---|------|------|------|-----|-----|--------|"
                      "---------|-----|-----------|---------|------|")
        for i, (_, r) in enumerate(scored.iterrows()):
            def _f(v, fmt=".1f"):
                return f"{v:{fmt}}" if v is not None and v == v else "—"

            lines.append(
                f"| {i+1} | {r.get('ticker','')} | {r.get('name','')} "
                f"| {r.get('market','')} "
                f"| {_f(r.get('pb'), '.2f')} "
                f"| {_f(r.get('roe'))}% "
                f"| {_f(r.get('dividend_yield'))}% "
                f"| {_f(r.get('fcf_yield'))}% "
                f"| {_f(r.get('penetration_R'))}% "
                f"| {_f(r.get('ev_ebitda'), '.1f')} "
                f"| {_f(r.get('floor_premium'))}% "
                f"| {_f(r.get('composite_score'))} |"
            )

    lines += [
        "",
        "## 说明",
        "",
        "- **穿透率 R%**: AA × M / 市值，R < Rf 标记 Low-Return",
        "- **底价溢价**: (当前价/底价 - 1) × 100%，越低越安全",
        "- **评分公式**: ROE(20%) + FCF收益率(20%) + 穿透率R(25%) "
        "+ EV/EBITDA逆序(15%) + 底价溢价逆序(20%)",
        "",
        "---",
        f"*由 screener 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="选股器统一入口")
    parser.add_argument("--market", default="ALL",
                        choices=["A", "HK", "US", "ALL"],
                        help="目标市场 (默认 ALL)")
    parser.add_argument("--tier1-only", action="store_true",
                        help="仅执行 Tier 1")
    parser.add_argument("--top", type=int, default=20,
                        help="输出 Top N (默认 20)")
    parser.add_argument("--output-dir", default="output/screener",
                        help="输出目录")
    args = parser.parse_args()

    run_pipeline(
        market=args.market,
        tier1_only=args.tier1_only,
        top_n=args.top,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
