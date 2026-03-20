# 公司财报分析工作区

基于 GitHub Copilot + MCP 工具链的公司财报分析环境，专为重度 token 消耗的深度分析任务优化。支持 A 股和港股的财报下载、PDF 结构化提取、深度财务分析及烟蒂股量化分析。

[English](README.en.md)

## 为什么用这套方案

**GitHub Copilot 按次计费**，不按 token 量收费，这意味着分析一份几十页的财报和分析几句话的成本是一样的。这种计费模式特别适合做公司研究这类需要大量上下文、消耗大量 token 的任务。

但 Copilot 原生有两个缺口需要弥补：

1. **不支持直接读取 PDF**：财报通常是 PDF 格式，需要工具将其转换为可读文本
2. **联网搜索股价不可靠**：让模型直接去搜股价容易返回错误或过时数据

本项目通过两个 MCP 工具解决这两个问题，并在此基础上封装了一套自动化的财报分析工作流。

## 项目结构

```
copilot-buttAnalysis/
├── .github/
│   ├── copilot-instructions.md     # Copilot 全局指令
│   ├── agents/                     # Agent 定义（report-fetcher / pdf-extractor / financial-analyst）
│   └── skills/                     # Skill 定义
│       ├── cigbutt-analysis/       # 烟蒂股量化分析
│       ├── coordinator/            # 财报分析协调器（三阶段编排）
│       ├── download-report/        # 财报下载（含 query_report.py / download_report.py）
│       └── financial-analysis/     # 财报深度分析
├── scripts/
│   ├── config.py                   # PDF 校验工具
│   └── pdf_preprocessor.py         # PDF 章节提取引擎
├── tools/
│   └── yahoo-finance-mcp/          # Yahoo Finance MCP 服务（本地副本）
├── report/                         # 存放财报 PDF（已 gitignore）
├── tempFile/                       # 中间产物：sections.json / data_pack.md / 分析报告（已 gitignore）
├── .vscode/
│   └── mcp.json                    # MCP 服务配置
├── README.md                       # 中文文档
└── README.en.md                    # 英文文档
```

## MCP 工具

### markitdown-mcp
将 PDF（及其他格式文件）转换为 Markdown 文本，供 Copilot 直接阅读分析。

- 项目地址：https://github.com/microsoft/markitdown
- 安装：`pip install markitdown-mcp`

### yfinance-mcp
通过 Yahoo Finance API 拉取实时及历史股价数据，避免模型凭空捏造数据。

- 项目地址：https://github.com/Alex2Yang97/yahoo-finance-mcp
- 功能：历史股价、财务指标、财务报表、期权数据、分析师评级等

## 内置 Skill

| Skill | 说明 | 触发方式 |
|-------|------|----------|
| **coordinator** | 财报分析协调器，自动编排三阶段流程：下载 → 提取 → 分析 | `分析 000651 2024年报` |
| **cigbutt-analysis** | 烟蒂股（深度价值）量化分析，含 T0/T1/T2 NAV、三大支柱、22 项 Fact Check | `对 000651 做烟蒂股分析` |
| **download-report** | 财报 PDF 下载，A 股调用巨潮网 API，港股通过雪球/同花顺搜索 | `下载 000651 2024 年报` |
| **financial-analysis** | 财报深度分析，覆盖盈利能力、现金流取证、分红、资产负债、管理层展望 | `分析 report/000651_2024_年报.pdf` |

## 内置 Agent

| Agent | 说明 |
|-------|------|
| **report-fetcher** | 检查/下载财报 PDF 到 `report/` 目录 |
| **pdf-extractor** | 运行 `pdf_preprocessor.py` 生成 `_sections.json`，再提取 6 类关键数据生成 `_data_pack.md` |
| **financial-analyst** | 读取 PDF + data pack，输出完整分析报告到 `tempFile/` |

三个 Agent 由 coordinator skill 自动按顺序调度，也可以单独调用。

## 环境配置

### 前置要求

- **Python 3.11+**（推荐通过 [conda](https://docs.conda.io/) 或 [miniconda](https://docs.anaconda.com/miniconda/) 管理）
- **VS Code** + **GitHub Copilot** 扩展（需有效订阅）
- **网络代理**（可选）：yfinance 需要访问 Yahoo Finance，国内网络可能需要代理

### 1. 创建 conda 环境

```bash
conda create -n analysis python=3.11 -y
conda activate analysis
```

### 2. 安装 Python 依赖

```bash
# markitdown MCP 服务
pip install markitdown-mcp

# yfinance MCP 服务依赖
pip install mcp[cli] yfinance

# PDF 处理依赖（pdf_preprocessor.py 使用）
pip install pdfplumber PyMuPDF
```

### 3. 克隆本项目

```bash
git clone <本项目地址>
cd copilot-buttAnalysis
```

`tools/yahoo-finance-mcp/` 已包含在本仓库内，无需额外克隆。

### 4. 配置 MCP 服务（.vscode/mcp.json）

项目已包含 `.vscode/mcp.json`，使用 `conda run` 方式启动 MCP 服务：

```json
{
  "servers": {
    "markitdown": {
      "type": "stdio",
      "command": "conda",
      "args": ["run", "-n", "analysis", "--no-capture-output", "markitdown-mcp"]
    },
    "yfinance": {
      "type": "stdio",
      "command": "conda",
      "args": [
        "run", "-n", "analysis", "--no-capture-output",
        "python", "${workspaceFolder}/tools/yahoo-finance-mcp/server.py"
      ],
      "env": {
        "HTTP_PROXY": "http://127.0.0.1:5780",
        "HTTPS_PROXY": "http://127.0.0.1:5780"
      }
    }
  }
}
```

**需要根据你的环境修改：**
- conda 环境名（默认 `analysis`）：若使用其他环境名，替换 `args` 中的 `analysis`
- 代理地址（`env` 部分）：若不需要代理可删除 `env` 块；若使用不同代理端口请相应修改

### 5. 验证 MCP 服务

在 VS Code 中打开本项目，打开 Copilot Chat，尝试以下操作确认服务正常：

```
获取 000651.SZ 的最新股价
```

如果返回了股价数据，说明 yfinance MCP 正常工作。

## 使用方法

### 一键财报分析（推荐）

直接告诉 Copilot 要分析哪只股票，coordinator 会自动完成 下载 → 提取 → 分析 全流程：

```
分析 000651 2024年报
```

```
分析 87001 2024 年报
```

### 单步操作

也可以分步执行：

**下载财报：**
```
下载 000651 2024 年报
```

**分析已有 PDF：**
```
帮我分析一下 report/000651_2024_年报.pdf 的财务状况
```

**查询股价数据：**
```
获取 87001.HK 最近一个月的股价走势
```

**烟蒂股量化分析：**
```
对 000651 做烟蒂股分析
```

### PDF 预处理脚本（手动）

如果需要单独运行 PDF 章节提取：

```bash
conda activate analysis
python3 scripts/pdf_preprocessor.py \
  --pdf report/000651_2024_年报.pdf \
  --output tempFile/000651_2024_年报_sections.json \
  --verbose
```

脚本会从 PDF 中提取 7 个目标章节（受限资产、应收账款账龄、关联交易、或有负债、非经常性损益、管理层讨论、子公司信息）并输出为结构化 JSON。

## 注意事项

### 股票代码格式
- **A 股**：6 位数字，如 `000651`（格力电器）、`600519`（贵州茅台）
- **港股**：1-5 位数字，如 `87001`（汇贤产业信托）；查询 yfinance 时需加后缀 `.HK`

### yfinance 数据
- Yahoo Finance 对港股的支持有限，部分港股可能无法获取完整数据
- 如果在国内网络无法访问 Yahoo Finance，需在 `mcp.json` 中配置代理
- yfinance 返回的数据可能存在延迟，不适合作为实时交易依据

### PDF 处理
- `pdf_preprocessor.py` 使用 pdfplumber 提取文本，如果 PDF 是扫描件（图片型）则无法提取
- 对于加密或受保护的 PDF，需先解除限制
- 如果 pdfplumber 提取质量较差（超过 30% 页面乱码），脚本会自动回退到 PyMuPDF

### 文件管理
- `report/` 目录存放财报 PDF，已被 `.gitignore` 忽略，不会提交到仓库
- `tempFile/` 目录存放中间产物（JSON、data pack、分析报告），同样被忽略
- 如需保留分析结果，请手动将 `tempFile/` 中的文件复制到其他位置

### Copilot 使用
- 确保 VS Code 中 GitHub Copilot 扩展已启用并登录
- MCP 服务需要在 VS Code 中激活（首次使用时会自动提示）
- 分析大型 PDF 时建议使用 Claude 系列模型（上下文窗口更大）
- 烟蒂股分析流程较长，第一次运行时可能需要多轮对话
