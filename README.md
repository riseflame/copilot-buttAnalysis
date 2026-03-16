# 公司财报分析工作区

基于 GitHub Copilot + MCP 工具链的公司财报分析环境，专为重度 token 消耗的深度分析任务优化。

[English](README.en.md)

## 为什么用这套方案

**GitHub Copilot 按次计费**，不按 token 量收费，这意味着分析一份几十页的财报和分析几句话的成本是一样的。这种计费模式特别适合做公司研究这类需要大量上下文、消耗大量 token 的任务。

但 Copilot 原生有两个缺口需要弥补：

1. **不支持直接读取 PDF**：财报通常是 PDF 格式，需要工具将其转换为可读文本
2. **联网搜索股价不可靠**：让模型直接去搜股价容易返回错误或过时数据

本项目通过两个 MCP 工具解决这两个问题。

## MCP 工具

### markitdown-mcp
将 PDF（及其他格式文件）转换为 Markdown 文本，供 Copilot 直接阅读分析。

- 项目地址：https://github.com/microsoft/markitdown
- 安装：`pip install markitdown-mcp`

### yfinance-mcp
通过 Yahoo Finance API 拉取实时及历史股价数据，避免模型凭空捏造数据。

- 项目地址：https://github.com/Alex2Yang97/yahoo-finance-mcp
- 功能：历史股价、财务指标、财务报表、期权数据、分析师评级等

## 安装

### 前置要求

- Python 3.11+（推荐通过 conda 管理）
- GitHub Copilot 订阅

### 1. 安装 markitdown-mcp

```bash
pip install markitdown-mcp
```

### 2. 安装 yfinance-mcp

```bash
git clone https://github.com/Alex2Yang97/yahoo-finance-mcp.git
cd yahoo-finance-mcp
pip install mcp[cli] yfinance
```

### 3. 配置 MCP（.vscode/mcp.json）

```json
{
  "servers": {
    "markitdown": {
      "type": "stdio",
      "command": "/path/to/conda/envs/your-env/bin/markitdown-mcp"
    },
    "yfinance": {
      "type": "stdio",
      "command": "/path/to/conda/envs/your-env/bin/python",
      "args": [
        "/absolute/path/to/yahoo-finance-mcp/server.py"
      ]
    }
  }
}
```

> 用 `which markitdown-mcp` 和 `which python` 确认正确路径。

## 使用方法

1. 将财报 PDF 拖入本项目目录
2. 在 Copilot Chat 中直接提问，例如：
   - `帮我分析一下汇贤25年中.pdf 的财务状况`
   - `获取 87001.HK 最近一个月的股价走势`
   - `对比财报中的数据和当前市场估值`

Copilot 会自动调用 markitdown 读取 PDF、调用 yfinance 获取股价，综合分析后给出结论。
