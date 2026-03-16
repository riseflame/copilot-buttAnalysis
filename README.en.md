# Company Financial Analysis Workspace

A financial report analysis environment built on GitHub Copilot + MCP toolchain, optimized for deep analysis tasks with heavy token consumption.

[中文](README.md)

## Why This Setup

**GitHub Copilot charges per request, not per token.** This means analyzing a 50-page financial report costs the same as a one-line question. That pricing model is a perfect fit for company research tasks that require massive context and generate enormous token usage.

However, Copilot has two gaps out of the box that need to be filled:

1. **No native PDF support**: Financial reports are almost always PDFs, so a tool is needed to convert them into readable text.
2. **Unreliable online search for stock data**: Asking the model to search for stock prices online often returns stale or hallucinated data.

This project bridges both gaps with two MCP tools.

## MCP Tools

### markitdown-mcp
Converts PDF (and other file formats) into Markdown text so Copilot can read and analyze them directly.

- Project: https://github.com/microsoft/markitdown
- Install: `pip install markitdown-mcp`

### yfinance-mcp
Pulls real-time and historical stock data via the Yahoo Finance API, eliminating the risk of the model fabricating numbers.

- Project: https://github.com/Alex2Yang97/yahoo-finance-mcp
- Capabilities: historical prices, financial metrics, financial statements, options data, analyst ratings, and more

## Installation

### Prerequisites

- Python 3.11+ (conda recommended)
- GitHub Copilot subscription

### 1. Install markitdown-mcp

```bash
pip install markitdown-mcp
```

### 2. Install yfinance-mcp

```bash
git clone https://github.com/Alex2Yang97/yahoo-finance-mcp.git
cd yahoo-finance-mcp
pip install mcp[cli] yfinance
```

### 3. Configure MCP (.vscode/mcp.json)

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

> Run `which markitdown-mcp` and `which python` to get the correct paths.

## Usage

1. Drop a financial report PDF into the project directory
2. Ask Copilot Chat directly, for example:
   - `Analyze the financial condition in HuiXian-2025H1.pdf`
   - `Get the price trend of 87001.HK over the last month`
   - `Compare the figures in the report against current market valuation`

Copilot will automatically call markitdown to read the PDF and yfinance to fetch stock data, then synthesize both into a comprehensive analysis.
