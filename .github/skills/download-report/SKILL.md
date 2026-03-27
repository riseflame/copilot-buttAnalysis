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

### Important: Distinguish Report Types

港股有两类重要文件，搜索策略不同：

| 类型 | 英文关键词 | 中文关键词 | 发布时间 | 内容 |
|------|-----------|-----------|---------|------|
| **业绩公告** (Results Announcement) | `annual results` / `interim results` | 全年业绩 / 中期业绩 | 财年结束后 ~3个月 | 精简版，含P&L、资产负债表、分红 |
| **年度报告** (Annual Report) | `annual report` | 年度报告 / 年报 | 业绩公告后 ~1-2个月 | 完整版，含附注、管理层讨论 |

**若用户要求的是"业绩公告"或刚公布不久的业绩**，优先搜索 Results Announcement。
**若用户要求"年报"且发布已超过2个月**，搜索 Annual Report 完整版。

### Search Strategy（按优先级顺序）

#### ① HKEXnews 直接搜索（推荐，最可靠）

使用 **Yahoo Search** 搜索 HKEXnews 上的 PDF（Yahoo Search 对 hkexnews 索引最好，Google/Bing 经常被 JS 挑战拦截）：

```
site:hkexnews.hk {formatted_code} {year} annual results announcement
```

例如搜索中国民航信息网络 2025 业绩公告：
```
site:hkexnews.hk 00696 2025 annual results announcement
```

**HKEXnews URL 格式规律：**
```
https://www1.hkexnews.hk/listedco/listconews/sehk/{YYYY}/{MMDD}/{YYYYMMDD}{5位序号}.pdf
```
- `{YYYY}` = 发布年份
- `{MMDD}` = 发布月日
- `{YYYYMMDD}{5位序号}` = 日期+递增序号

> **实战经验**：2025年度业绩通常在2026年3-4月发布，所以 URL 中的年份是发布年而非报告年。

#### ② 雪球搜索

```
site:stockn.xueqiu.com {formatted_code} annual report {year}
```

#### ③ 同花顺搜索

```
site:notice.10jqka.com.cn {formatted_code} {search_keyword} {year}
```

#### ④ 通用搜索（兜底）

如以上均无结果，去掉 `site:` 限制做通用搜索。

### Search Engine Selection

| 搜索引擎 | 适用场景 | 注意事项 |
|----------|---------|---------|
| **Yahoo Search** | 搜 hkexnews.hk PDF | ✅ 最佳，直接返回 PDF 链接 |
| **Bing** | 搜雪球/同花顺 | ⚠️ 搜 hkexnews 时常被 JS 挑战拦截 |
| **Google** | 通用兜底 | ⚠️ 同上，且可能需要 CAPTCHA |

**Yahoo Search URL 构造：**
```
https://search.yahoo.com/search?p={url_encoded_query}
```

### If no year was specified:
1. Try current year first
2. If no results, try previous year
3. Pick the most recent matching result

## Step 3: Extract PDF Links (HK only)

From the search results, filter URLs that match PDF links from supported sources:
```
https://www1.hkexnews.hk/listedco/listconews/sehk/.../*.pdf   ← 首选
https://stockn.xueqiu.com/.../*.pdf
https://notice.10jqka.com.cn/.../*.pdf
```

> **优先选择 hkexnews.hk 链接**：这是港交所官方披露平台，数据最权威、最完整。

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

**支持的 URL 来源（download_report.py 白名单）：**
- `stockn.xueqiu.com`
- `notice.10jqka.com.cn` / `*.10jqka.com.cn`
- `static.cninfo.com.cn`
- `www1.hkexnews.hk` / `www.hkexnews.hk`

> **⚠️ 网络问题处理**：若终端无法访问外网（DNS 解析失败），可使用 `open_browser_page` 工具在用户浏览器中打开 PDF URL，提示用户手动保存到 `report/` 目录。

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