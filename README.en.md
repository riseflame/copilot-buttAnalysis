# Company Financial Analysis Workspace

A financial report analysis environment built on GitHub Copilot + MCP toolchain, optimized for deep analysis tasks with heavy token consumption. Supports A-share and Hong Kong stock report downloading, PDF structured extraction, deep financial analysis, and cigar butt (deep value) quantitative analysis.

[中文](README.md)

## Why This Setup

**GitHub Copilot charges per request, not per token.** This means analyzing a 50-page financial report costs the same as a one-line question. That pricing model is a perfect fit for company research tasks that require massive context and generate enormous token usage.

However, Copilot has two gaps out of the box that need to be filled:

1. **No native PDF support**: Financial reports are almost always PDFs, so a tool is needed to convert them into readable text.
2. **Unreliable online search for stock data**: Asking the model to search for stock prices online often returns stale or hallucinated data.

This project bridges both gaps with two MCP tools, and builds an automated financial analysis workflow on top.

## Project Structure

```
copilot-buttAnalysis/
├── .github/
│   ├── copilot-instructions.md     # Global Copilot instructions
│   ├── agents/                     # Agent definitions (report-fetcher / pdf-extractor / financial-analyst)
│   └── skills/                     # Skill definitions
│       ├── cigbutt-analysis/       # Cigar butt / deep value quantitative analysis
│       ├── coordinator/            # Financial analysis coordinator (3-phase orchestration)
│       ├── download-report/        # Report download (includes query_report.py / download_report.py)
│       └── financial-analysis/     # Deep financial analysis
├── scripts/
│   ├── config.py                   # PDF validation utility
│   └── pdf_preprocessor.py         # PDF section extraction engine
├── tools/
│   └── yahoo-finance-mcp/          # Yahoo Finance MCP server (local copy)
├── report/                         # Financial report PDFs (gitignored)
├── tempFile/                       # Intermediate outputs: sections.json / data_pack.md / analysis reports (gitignored)
├── .vscode/
│   └── mcp.json                    # MCP server configuration
├── README.md                       # Chinese documentation
└── README.en.md                    # English documentation
```

## MCP Tools

### markitdown-mcp
Converts PDF (and other file formats) into Markdown text so Copilot can read and analyze them directly.

- Project: https://github.com/microsoft/markitdown
- Install: `pip install markitdown-mcp`

### yfinance-mcp
Pulls real-time and historical stock data via the Yahoo Finance API, eliminating the risk of the model fabricating numbers.

- Project: https://github.com/Alex2Yang97/yahoo-finance-mcp
- Capabilities: historical prices, financial metrics, financial statements, options data, analyst ratings, and more

## Built-in Skills

| Skill | Description | How to Trigger |
|-------|-------------|----------------|
| **coordinator** | Financial analysis coordinator — auto-orchestrates 3-phase workflow: download → extract → analyze | `分析 000651 2024年报` |
| **cigbutt-analysis** | Cigar butt (deep value) quantitative analysis — T0/T1/T2 NAV, three pillars, 22-item Fact Check | `对 000651 做烟蒂股分析` |
| **download-report** | Report PDF download — A-shares via cninfo API, HK stocks via xueqiu/10jqka search | `下载 000651 2024 年报` |
| **financial-analysis** | Deep financial analysis — profitability, cash flow forensics, dividends, balance sheet, management outlook | `分析 report/000651_2024_年报.pdf` |

## Built-in Agents

| Agent | Description |
|-------|-------------|
| **report-fetcher** | Check for / download financial report PDFs to the `report/` directory |
| **pdf-extractor** | Run `pdf_preprocessor.py` to produce `_sections.json`, then extract 6 categories of key data into `_data_pack.md` |
| **financial-analyst** | Read PDF + data pack and output a full analysis report to `tempFile/` |

The three agents are orchestrated automatically by the coordinator skill, but can also be invoked individually.

## Environment Setup

### Prerequisites

- **Python 3.11+** (managed via [conda](https://docs.conda.io/) or [miniconda](https://docs.anaconda.com/miniconda/) recommended)
- **VS Code** + **GitHub Copilot** extension (active subscription required)
- **Network proxy** (optional): yfinance needs access to Yahoo Finance, which may require a proxy in some regions

### 1. Create a conda environment

```bash
conda create -n analysis python=3.11 -y
conda activate analysis
```

### 2. Install Python dependencies

```bash
# markitdown MCP server
pip install markitdown-mcp

# yfinance MCP server dependencies
pip install mcp[cli] yfinance

# PDF processing dependencies (used by pdf_preprocessor.py)
pip install pdfplumber PyMuPDF
```

### 3. Clone the repository

```bash
git clone <repository-url>
cd copilot-buttAnalysis
```

`tools/yahoo-finance-mcp/` is already included in the repository — no separate clone needed.

### 4. Configure MCP servers (.vscode/mcp.json)

The project ships with a `.vscode/mcp.json` that launches MCP servers via `conda run`:

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

**Adjust for your environment:**
- **Conda env name** (default `analysis`): replace `analysis` in `args` if you used a different name
- **Proxy** (`env` section): remove the `env` block if no proxy is needed, or change the port to match your setup

### 5. Verify MCP servers

Open the project in VS Code, launch Copilot Chat, and try:

```
Get the latest stock price for 000651.SZ
```

If stock data is returned, yfinance MCP is working correctly.

## Usage

### One-click Financial Analysis (Recommended)

Tell Copilot which stock to analyze — the coordinator will automatically handle the full download → extract → analyze pipeline:

```
分析 000651 2024年报
```

```
分析 87001 2024 年报
```

### Step-by-step Operations

You can also run each phase individually:

**Download a report:**
```
下载 000651 2024 年报
```

**Analyze an existing PDF:**
```
Analyze the financial condition in report/000651_2024_年报.pdf
```

**Query stock data:**
```
Get the price trend of 87001.HK over the last month
```

**Cigar butt quantitative analysis:**
```
对 000651 做烟蒂股分析
```

### Manual PDF Preprocessing

To run the section extraction script standalone:

```bash
conda activate analysis
python3 scripts/pdf_preprocessor.py \
  --pdf report/000651_2024_年报.pdf \
  --output tempFile/000651_2024_年报_sections.json \
  --verbose
```

The script extracts 7 target sections from the PDF (restricted assets, AR aging, related party transactions, contingent liabilities, non-recurring items, management discussion & analysis, subsidiary information) and outputs structured JSON.

## Important Notes

### Stock Code Formats
- **A-shares**: 6-digit codes, e.g. `000651` (Gree Electric), `600519` (Kweichow Moutai)
- **HK stocks**: 1-5 digit codes, e.g. `87001` (Hui Xian REIT); append `.HK` suffix when querying yfinance

### yfinance Data
- Yahoo Finance has limited coverage for some HK-listed stocks — data may be incomplete
- If Yahoo Finance is inaccessible from your network, configure a proxy in `mcp.json`
- Data from yfinance may be delayed and should not be used for real-time trading decisions

### PDF Processing
- `pdf_preprocessor.py` uses pdfplumber for text extraction — scanned (image-based) PDFs are not supported
- Encrypted or protected PDFs must be unlocked before processing
- If pdfplumber extraction quality is poor (>30% garbled pages), the script automatically falls back to PyMuPDF

### File Management
- `report/` stores financial report PDFs and is gitignored — files won't be committed to the repository
- `tempFile/` stores intermediate outputs (JSON, data packs, analysis reports) and is also gitignored
- To preserve analysis results, manually copy files from `tempFile/` to another location

### Copilot Usage
- Ensure the GitHub Copilot extension is enabled and signed in within VS Code
- MCP servers need to be activated in VS Code (you'll be prompted on first use)
- For large PDFs, Claude-series models are recommended (larger context window)
- The cigar butt analysis workflow is lengthy — the first run may require multiple conversation turns
