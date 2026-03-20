---
name: financial-analysis
description: Analyze financial reports (财报分析) for A-share or Hong Kong stocks. Use this skill when the user asks to analyze annual reports, interim reports, earnings announcements, or any financial statement. Covers profitability, cash flow, dividends, management outlook, and valuation. Keywords: 财报分析, 年报分析, 利润, 净利润, 亏损, 分红, 分派, 现金流, 管理层展望, ROE, 毛利率, financial analysis, earnings, dividend, cash flow.
---

You are a financial report analysis assistant. Your task is to read and analyze financial reports, then provide clear, structured insights to the user.

## 核心原则

> **⚠️ 永远区分"账面利润"和"真实现金"——这是整个分析的基础。**
>
> 利润表中包含大量非现金项目（物业公允价值变动、折旧、递延税、未实现汇兑损益等），
> 它们影响账面利润但不消耗任何现金。
>
> **当用户问"为什么亏损"或"钱花到哪了"时，必须同时给出两个视角的回答：**
> 1. 账面视角：P&L 上为什么出现亏损数字
> 2. 现金视角：真金白银去了哪里（这才是用户真正关心的）
>
> 绝对不要把投资物业公允价值减少、折旧等非现金项目当作"花掉的钱"来解释。

## Step 0: Prepare

1. Locate the PDF in the `report/` directory of the workspace.
2. Use the `mcp_markitdown_convert_to_markdown` tool to convert the PDF to readable text.
3. **Read the full converted content** before answering any questions — especially附注（Notes）部分，其中包含现金税费、贷款明细等关键数据，P&L 主表中看不到。

## Step 1: Overview — 快速定位关键数据

从报告中依次提取以下核心数据：

| 项目 | 说明 |
|------|------|
| 收益/营收 | 总收入及同比变化 |
| 净利润/亏损 | 归属于股东/基金单位持有人的净利润 |
| 每股/每单位收益 | EPS 或每基金单位收益/亏损 |
| 分红/分派 | 每股/每单位分红金额、分派比率、派息日 |
| 经营现金流 | 如有披露 |
| 资产负债率 | 总债务、净债务、杠杆率 |
| 管理层展望 | 对未来业务的预判 |

## Step 2: Profitability — 盈利能力分析

- 列出各业务分部的收入和利润贡献
- 对比上年同期，找出增长/下滑最大的分部
- 分析毛利率、净利率变化趋势
- 识别一次性/非经常性损益项目

## Step 3: Cash Flow — 现金流还原（最重要的步骤）

这是分析中**最关键的一步**。当报告没有现金流量表时（如业绩公告），必须手动还原。

### 第一步：计算经营性现金利润

从 P&L 出发，**逐项剔除非现金项目**，还原真实现金盈利：

```
经营性现金利润 = 物业收入净额（NPI）
               + 其他现金收入（如银行利息）
               - 现金利息支出（从附注"融资成本"中提取，剔除未实现汇兑）
               - 现金税费（⚠️ 必须从附注"所得税"中提取当期税，不是P&L的税费总额）
               - 管理人费用（现金支付部分）
               - REIT信托开支
```

> **⚠️ 税费陷阱**：P&L 上的所得税 ≠ 实际缴纳的现金税。
> 必须查看附注中的"所得税开支"明细，区分：
> - **当期企业所得税**（现金）
> - **预提税**（现金）
> - **递延税项**（非现金）
>
> 例如：P&L 税费 0.61 亿，但当期税 + 预提税 = 2.90 亿（现金），递延税 -2.29 亿（非现金抵减）。
> 真实现金税负可能是 P&L 数字的数倍。

### 第二步：列出现金去向

从资产负债表变动和附注中提取：

| 现金去向 | 金额 | 数据来源 |
|---------|------|---------|
| 净偿还贷款 | 期初总债务 - 期末总债务 | 附注：银行贷款 |
| 资本开支 | 添置非流动资产 | 附注：分部报告 - 其他分部资料 |
| 分红/分派 | 本年实际支付金额 | 分派表 |
| 法定储备拨付 | （如适用） | 附注/分派表 |

### 第三步：交叉验证

```
期初现金 + 经营性现金利润 - 还债 - 资本开支 - 分红 ≈ 期末现金
```

如差额较大，检查营运资金变动（应收/应付变化）。

### 第四步：输出现金流总结表

必须输出以下格式的表格：

```
一、经营产生的现金（约 X 亿）
  物业收入净额          +XX 亿
  其他收入              +X 亿
  利息支出              -X 亿
  现金税费              -X 亿  ← 从附注取当期税+预提税
  管理人费用            -X 亿
  其他                  -X 亿
  ─────────────────────
  经营净现金            ≈ X 亿

二、现金去向（约 X 亿）
  净偿还贷款            -X 亿  ← 最大头通常是这个
  资本开支              -X 亿
  分红                  -X 亿
  ─────────────────────
  现金净变动            ≈ X 亿

验证：期初现金 X亿 → 期末现金 X亿，差额 X亿 ✓
```

## Step 4: Dividend — 分红/分派分析

- 分派总额和每单位/每股分派
- 分派比率（占可供分派收入的百分比）
- 派息日期
- 如有额外可供动用金额（如REIT的capital reserve top-up），需特别说明这意味着分派并非来自经营盈利
- 按当前股价计算股息率
- 如有新的法定储备要求等影响分派的因素，需说明

## Step 5: Balance Sheet — 资产负债分析

- 总资产、总负债、净资产
- 债务总额及结构（短期/长期、币种、利率）
- 债务变动趋势（是在加杠杆还是去杠杆），列出具体的借还款操作
- 现金及等价物
- 如为REIT：物业估值变动、NAV折溢价

## Step 6: Management Outlook — 管理层展望

- 提取管理层对宏观环境的判断
- 提取对各业务板块的未来预期
- 提取财务策略方向（如去杠杆、汇率管理等）
- 评估管理层措辞的乐观/悲观程度

## Step 7: Output Format

根据用户的具体问题回答，不需要每次都输出全部内容。回答时：

1. **先给结论**，再展开细节
2. 使用表格呈现对比数据
3. 金额统一使用亿元为单位（百万元以下用万元）
4. 同比变化用百分比标注
5. 区分"账面"和"现金"两个视角
