"""
选股器配置 — 三市场筛选参数

参考龟龟投资策略 screener_config.py，
适配烟蒂股选股场景（破净、高股息、低估值）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketParams:
    """单个市场的筛选参数。"""
    max_pb: float = 1.5
    max_pe: float = 30.0
    allow_negative_pe: bool = True       # 允许亏损/负PE进入观察通道
    min_dividend_yield: float = 0.01     # 最低股息率 (1%)
    require_dividend: bool = True        # 是否强制要求有股息
    min_market_cap: float = 1e9          # 最低市值（本地货币）
    currency_label: str = "RMB"

    # Tier 2 财务质量门槛
    min_roe: float = 5.0                 # 最低 ROE (%)
    min_gross_margin: float = 15.0       # 最低毛利率 (%)
    max_debt_ratio: float = 70.0         # 最高资产负债率 (%)
    dividend_tax_rate: float = 0.0       # 股息税率

    # 无风险利率（用于穿透率 R 否决门 & 底价计算）
    risk_free_rate: float = 3.0          # %


# ── 三市场预设 ────────────────────────────────────────────

A_SHARE_PARAMS = MarketParams(
    max_pb=1.0,                   # 烟蒂股：破净为主
    max_pe=15.0,                  # 烟蒂股：低估值
    allow_negative_pe=True,
    min_dividend_yield=0.02,      # 要求 2%
    require_dividend=True,
    min_market_cap=1e9,           # 10 亿 RMB（覆盖中小盘）
    currency_label="RMB",
    min_roe=3.0,                  # 烟蒂股场景降低门槛
    min_gross_margin=5.0,         # 重资产周期股毛利率天然偏低
    max_debt_ratio=70.0,
    dividend_tax_rate=0.0,
    risk_free_rate=3.0,
)

HK_SHARE_PARAMS = MarketParams(
    max_pb=1.0,                   # 烟蒂股：破净为主
    max_pe=15.0,                  # 烟蒂股：低估值
    allow_negative_pe=True,
    min_dividend_yield=0.02,      # 港股要求 2%
    require_dividend=True,
    min_market_cap=1e8,           # 1 亿 HKD（覆盖中小盘深度价值）
    currency_label="HKD",
    min_roe=3.0,                  # 烟蒂股场景降低门槛
    min_gross_margin=5.0,         # 周期股/银行毛利率低
    max_debt_ratio=80.0,
    dividend_tax_rate=0.0,        # 港股通暂按 0%
    risk_free_rate=3.0,
)

US_SHARE_PARAMS = MarketParams(
    max_pb=1.5,
    max_pe=25.0,
    allow_negative_pe=True,
    min_dividend_yield=0.0,       # 美股不强制分红
    require_dividend=False,
    min_market_cap=5e8,           # 5 亿 USD
    currency_label="USD",
    min_roe=6.0,
    min_gross_margin=15.0,
    max_debt_ratio=65.0,
    dividend_tax_rate=0.10,       # 美股预扣 10%
    risk_free_rate=4.0,
)

MARKET_PARAMS: dict[str, MarketParams] = {
    "A": A_SHARE_PARAMS,
    "HK": HK_SHARE_PARAMS,
    "US": US_SHARE_PARAMS,
}


def get_params(market: str) -> MarketParams:
    """获取指定市场的筛选参数。"""
    return MARKET_PARAMS.get(market.upper(), A_SHARE_PARAMS)


@dataclass
class ScreenerConfig:
    """全局选股器配置。"""

    # Tier 2 评分权重（参考龟龟选股器）
    weight_roe: float = 0.20
    weight_fcf_yield: float = 0.20
    weight_penetration_r: float = 0.25
    weight_ev_ebitda: float = 0.15
    weight_floor_premium: float = 0.20

    # 输出
    top_n: int = 20                      # 最终输出 Top N
    output_dir: str = "output/screener"

    # yfinance 请求控制
    request_delay: float = 0.5           # 请求间隔（秒）
    max_retries: int = 2
