#!/usr/bin/env python3
"""
财报查询工具 (Financial Report Query Tool)

通过巨潮资讯网 (cninfo.com.cn) API 查询A股财报PDF下载链接。
支持年报、中报、一季报、三季报。

Usage:
    python3 query_report.py --stock-code 300750 --report-type 年报
    python3 query_report.py --stock-code 300750 --report-type 年报 --year 2024
    python3 query_report.py --stock-code 600887 --report-type 中报 --year 2024 --download --save-dir .
"""

import argparse
import json
import os
import re
import sys
import time

import requests

# ── Constants ────────────────────────────────────────────────────────────────

CNINFO_BASE = "http://www.cninfo.com.cn"
CNINFO_PDF_BASE = "http://static.cninfo.com.cn/"
SEARCH_URL = f"{CNINFO_BASE}/new/information/topSearch/query"
ANNOUNCEMENT_URL = f"{CNINFO_BASE}/new/hisAnnouncement/query"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0",
    "Accept": "*/*",
    "Referer": "http://www.cninfo.com.cn/",
    "Content-Type": "application/x-www-form-urlencoded",
}

REQUEST_TIMEOUT = 15

# A-share report type → cninfo category
CATEGORY_MAP = {
    "年报": "category_ndbg_szsh",
    "中报": "category_bndbg_szsh",
    "一季报": "category_yjdbg_szsh",
    "三季报": "category_sjdbg_szsh",
}

# Aliases
TYPE_ALIASES = {
    "annual": "年报",
    "interim": "中报",
    "q1": "一季报",
    "q3": "三季报",
    "半年报": "中报",
}

# Titles to exclude (摘要, auditor reports, ESG, etc.)
EXCLUDE_KEYWORDS = [
    "摘要", "审计", "公告", "利润分配", "可持续发展", "股东大会",
    "ESG", "summary", "auditor", "dividend", "更正", "补充",
    "意见", "内部控制", "社会责任", "评估报告", "鉴证报告",
]

# ── API Functions ────────────────────────────────────────────────────────────


def lookup_stock(stock_code):
    """Look up stock orgId and info from cninfo topSearch API.

    Returns dict with keys: code, orgId, zwjc (Chinese name), category, type
    or None if not found.
    """
    # Strip SH/SZ prefix if present
    raw_code = re.sub(r"^(SH|SZ)", "", stock_code, flags=re.IGNORECASE)

    resp = requests.post(
        SEARCH_URL,
        data={"keyWord": raw_code, "maxSecNum": 10, "maxListNum": 5},
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()

    if not results:
        return None

    # Find exact match for A-share
    for item in results:
        if item["code"] == raw_code and item.get("category") == "A股":
            return item

    # Fallback: first A-share result matching the code
    for item in results:
        if item["code"] == raw_code:
            return item

    return None


def query_announcements(stock_code, org_id, report_type, year=None):
    """Query cninfo announcement API for matching reports.

    Returns list of announcement dicts, sorted newest first.
    """
    category = CATEGORY_MAP.get(report_type)
    if not category:
        return []

    data = {
        "pageNum": 1,
        "pageSize": 30,
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": f"{stock_code},{org_id}",
        "searchkey": "",
        "secid": "",
        "category": category,
        "trade": "",
        "seDate": "",
        "sortName": "",
        "sortType": "",
        "isHLT": "",
    }

    resp = requests.post(
        ANNOUNCEMENT_URL,
        data=data,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    result = resp.json()

    announcements = result.get("announcements") or []
    return announcements


def filter_announcements(announcements, report_type, year=None):
    """Filter announcements to find the best matching report PDF.

    Excludes 摘要, audit reports, etc. Optionally filters by year.
    Returns filtered list sorted by relevance.
    """
    candidates = []
    for ann in announcements:
        title = ann.get("announcementTitle", "")
        # Exclude unwanted types
        if any(kw in title for kw in EXCLUDE_KEYWORDS):
            continue
        candidates.append(ann)

    if year:
        # Prefer results whose title contains the year
        year_str = str(year)
        year_matched = [a for a in candidates if year_str in a.get("announcementTitle", "")]
        if year_matched:
            candidates = year_matched

    return candidates


def format_code(stock_code):
    """Normalize stock code: strip SH/SZ prefix, return raw digits."""
    return re.sub(r"^(SH|SZ)", "", stock_code, flags=re.IGNORECASE)


def normalize_report_type(report_type):
    """Normalize report type to standard Chinese name."""
    lower = report_type.lower().strip()
    return TYPE_ALIASES.get(lower, report_type)


def detect_year_from_title(title):
    """Extract year from announcement title like '2024年年度报告'."""
    m = re.search(r"(20\d{2})\s*年", title)
    return m.group(1) if m else None


# ── Main ─────────────────────────────────────────────────────────────────────


def print_result(success, results=None, stock_code="", report_type="",
                 year="", message=""):
    """Print structured result block."""
    status = "SUCCESS" if success else "FAILED"
    print("\n---RESULT---")
    print(f"status: {status}")
    print(f"stock_code: {stock_code}")
    print(f"report_type: {report_type}")
    print(f"year: {year}")
    print(f"message: {message}")
    if results:
        print(f"count: {len(results)}")
        for i, r in enumerate(results):
            print(f"--- candidate {i} ---")
            print(f"title: {r['title']}")
            print(f"pdf_url: {r['pdf_url']}")
            print(f"size_kb: {r['size_kb']}")
            if r.get("year"):
                print(f"year: {r['year']}")
    else:
        print("count: 0")
    print("---END---")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Query A-share financial report PDFs via cninfo API"
    )
    parser.add_argument(
        "--stock-code", required=True,
        help="Stock code (e.g. 300750, SH600887, SZ000001)"
    )
    parser.add_argument(
        "--report-type", default="年报",
        help="Report type: 年报/中报/一季报/三季报/annual/interim/q1/q3"
    )
    parser.add_argument(
        "--year", default=None,
        help="Report year (e.g. 2024). If omitted, returns latest."
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Also download the best matching PDF"
    )
    parser.add_argument(
        "--save-dir", default="./report/",
        help="Directory to save the PDF (used with --download)"
    )
    args = parser.parse_args(argv)

    stock_code = args.stock_code
    report_type = normalize_report_type(args.report_type)
    year = args.year
    raw_code = format_code(stock_code)

    # Validate report type
    if report_type not in CATEGORY_MAP:
        print(f"Error: unsupported report type '{report_type}'", file=sys.stderr)
        print(f"Supported: {', '.join(CATEGORY_MAP.keys())}", file=sys.stderr)
        print_result(False, stock_code=raw_code, report_type=report_type,
                     year=year or "", message=f"Unsupported report type: {report_type}")
        sys.exit(1)

    # Step 1: Look up stock
    print(f"Looking up stock: {raw_code}", file=sys.stderr)
    stock_info = lookup_stock(raw_code)
    if not stock_info:
        msg = f"Stock not found: {raw_code}"
        print(f"Error: {msg}", file=sys.stderr)
        print_result(False, stock_code=raw_code, report_type=report_type,
                     year=year or "", message=msg)
        sys.exit(1)

    org_id = stock_info["orgId"]
    stock_name = stock_info.get("zwjc", "")
    print(f"Found: {raw_code} {stock_name} (orgId={org_id})", file=sys.stderr)

    # Step 2: Query announcements
    print(f"Querying {report_type} announcements...", file=sys.stderr)
    announcements = query_announcements(raw_code, org_id, report_type)
    if not announcements:
        msg = f"No {report_type} announcements found for {raw_code} {stock_name}"
        print(f"Error: {msg}", file=sys.stderr)
        print_result(False, stock_code=raw_code, report_type=report_type,
                     year=year or "", message=msg)
        sys.exit(1)

    print(f"Found {len(announcements)} announcements, filtering...", file=sys.stderr)

    # Step 3: Filter
    candidates = filter_announcements(announcements, report_type, year)
    if not candidates:
        msg = f"No matching {report_type} report found for {raw_code} {stock_name}"
        if year:
            msg += f" (year={year})"
        print(f"Error: {msg}", file=sys.stderr)
        print_result(False, stock_code=raw_code, report_type=report_type,
                     year=year or "", message=msg)
        sys.exit(1)

    # Build result list
    results = []
    for ann in candidates[:5]:
        title = ann["announcementTitle"]
        pdf_url = CNINFO_PDF_BASE + ann["adjunctUrl"]
        size_kb = ann.get("adjunctSize", 0)
        detected_year = detect_year_from_title(title) or year or ""
        results.append({
            "title": title,
            "pdf_url": pdf_url,
            "size_kb": size_kb,
            "year": detected_year,
        })

    best = results[0]
    result_year = best["year"] or year or ""

    print(f"\nBest match: {best['title']}", file=sys.stderr)
    print(f"PDF URL: {best['pdf_url']}", file=sys.stderr)
    print(f"Size: {best['size_kb']}KB", file=sys.stderr)

    # Step 4: Optionally download
    if args.download:
        _download_best(best, raw_code, report_type, result_year, args.save_dir)
    else:
        print_result(True, results=results, stock_code=raw_code,
                     report_type=report_type, year=result_year,
                     message=f"Found {len(results)} candidate(s) for {stock_name}")


def _download_best(best, raw_code, report_type, year, save_dir):
    """Download the best matching PDF using download_report.py logic."""
    from download_report import download_annual_report, build_filename, print_result as dl_print_result

    os.makedirs(save_dir, exist_ok=True)
    filename = build_filename(raw_code, report_type, year)
    save_path = os.path.join(save_dir, filename)

    pdf_url = best["pdf_url"]
    print(f"Downloading: {pdf_url}", file=sys.stderr)

    success, message, filesize = download_annual_report(
        url=pdf_url, save_path=save_path,
    )

    dl_print_result(
        success=success,
        filepath=os.path.abspath(save_path) if success else "",
        filesize=filesize,
        url=pdf_url,
        stock_code=raw_code,
        report_type=report_type,
        year=year,
        message=message,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
