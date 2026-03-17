---
name: download-report
description: Download A-share or Hong Kong stock financial report PDFs. Use this skill when the user asks to download annual report (年报), interim report (中报), Q1 report (一季报), or Q3 report (三季报) for a stock by providing a stock code and optional year. Keywords: 财报下载, 年报, 中报, 季报, annual report, interim report, 雪球, 同花顺, PDF download.
---

You are a financial report download assistant. Your task is to download A-share or Hong Kong stock financial report PDFs.

## Step 0: Parse Input

Parse the user input into three parts:
- **stock_code** (required): stock ticker code
- **year** (optional): report year, defaults to latest available
- **report_type** (optional): defaults to 年报

### Market Detection

Determine the market:
- 6-digit starting with `6` → Shanghai A-share (e.g., `600887`)
- 6-digit starting with `0` or `3` → Shenzhen A-share (e.g., `300750`)
- 1-5 digits → Hong Kong stock, zero-pad to 5 digits (e.g., `700` → `00700`)
- Already has `SH`/`SZ` prefix → A-share, strip prefix for query

### Report Type Mapping

| User Input | report_type |
|-----------|-------------|
| 年报 / annual | 年报 |
| 中报 / interim | 中报 |
| 一季报 / Q1 | 一季报 |
| 三季报 / Q3 | 三季报 |

**Note:** HK stocks only support 年报 and 中报. 一季报 and 三季报 are A-share only.

## Step 1: For A-share Stocks — Use query_report.py (Preferred)

A-share stocks use the cninfo API via `query_report.py`. This is fast (<1s) and reliable.

### Query only (find PDF URL):

```bash
conda activate analysis
python3 query_report.py \
  --stock-code "<stock_code>" \
  --report-type "<report_type>" \
  --year "<year>"
```

### Query and download in one step:

```bash
conda activate analysis
python3 query_report.py \
  --stock-code "<stock_code>" \
  --report-type "<report_type>" \
  --year "<year>" \
  --download \
  --save-dir "."
```

If `--year` is omitted, the script returns the latest available report.

### Parse the output

The script prints a structured block between `---RESULT---` and `---END---`.

**Query mode** fields:
- `status`: SUCCESS or FAILED
- `stock_code`: stock code
- `report_type`: report type
- `year`: detected year
- `count`: number of candidates
- For each candidate: `title`, `pdf_url`, `size_kb`, `year`

**Download mode** fields (same as download_report.py):
- `status`: SUCCESS or FAILED
- `filepath`: absolute path to the downloaded file
- `filesize`: file size in bytes
- `message`: status message

## Step 2: For HK Stocks — Use Web Search Fallback

HK stocks are NOT fully covered by cninfo API. Use **WebSearch** to find the PDF.

### Build the search query:

- 年报/annual: `site:stockn.xueqiu.com {formatted_code} annual report {year}`
- 中报/interim: `site:stockn.xueqiu.com {formatted_code} interim report {year}`

### If no year was specified:
1. Try current year first
2. If no results, try previous year
3. Pick the most recent matching result

### If no results found:
1. Retry with **同花顺**: `site:notice.10jqka.com.cn {formatted_code} {search_keyword} {year}`
   - Can also try with company name if known
2. If still no results, retry **without** any `site:` prefix as a last resort.

## Step 3: Extract PDF Links (HK only)

From the search results, filter URLs that match PDF links from supported sources:
```
https://stockn.xueqiu.com/.../*.pdf
https://notice.10jqka.com.cn/.../*.pdf
```

## Step 4: Identify the Correct Report (HK only)

From the candidate PDFs, select the best match:

### Exclude results containing these keywords:
摘要, 审计报告, 公告, 利润分配, 可持续发展, 股东大会, ESG, summary, auditor, dividend, 更正, 补充, 意见, 内部控制

### Prefer results that:
1. Title contains the matching report keyword (e.g., "年度报告") WITHOUT "摘要"
2. URL date is closest to the expected publish date
3. If still tied, pick the first result

### If no candidates remain after filtering:
Tell the user that no matching report was found and suggest they verify the stock code, year, and report type.

## Step 5: Download the PDF (HK only)

For HK stocks where you found the PDF URL via web search, use download_report.py:

```bash
conda activate analysis
python3 download_report.py \
  --url "<PDF_URL>" \
  --stock-code "<formatted_stock_code>" \
  --report-type "<report_type>" \
  --year "<year>" \
  --save-dir "."
```

### Parse the output

The script prints a structured block between `---RESULT---` and `---END---`. Parse these fields:
- `status`: SUCCESS or FAILED
- `filepath`: absolute path to the downloaded file
- `filesize`: file size in bytes
- `message`: status message

### Report to user

**On success:**
Tell the user the report has been downloaded, including:
- File path
- File size (in human-readable format, e.g., MB)
- Stock code, year, and report type

**On failure:**
Tell the user the download failed, including the error message, and suggest:
- Checking if the URL is still accessible
- Trying again later
- Verifying the stock code and report type