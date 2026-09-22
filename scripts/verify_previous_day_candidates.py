#!/usr/bin/env python3
"""Verify the previous trading day's seven-factor candidate pool.

The daily workflow first creates today's prediction data, then this script:
1. Finds the latest archived prediction before today's scan date.
2. Uses that prediction's complete candidate list as the verification universe.
3. Fetches today's closing quote for every predicted stock from Sina.
4. Calculates next-day performance from the prediction-day close to today's close.
5. Exports a standalone verification workbook.

This does not change the seven-factor scoring logic or today's prediction workbook.
"""

import json
import os
import re
import ssl
import time
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(DATA_DIR, "candidate_pool_validation")

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

DATE_RE = re.compile(r"seven_factor_(\d{4}-\d{2}-\d{2})\.json$")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def text(v):
    if v is None or v == "":
        return "-"
    return str(v)


def fetch_sina_quotes(codes, batch_size=80):
    """Fetch current quotes in batches using Sina's bulk quote endpoint."""
    quotes = {}
    unique_codes = []
    seen = set()
    for raw in codes:
        code = str(raw or "").strip()
        if code and code not in seen:
            seen.add(code)
            unique_codes.append(code)

    for start in range(0, len(unique_codes), batch_size):
        batch = unique_codes[start:start + batch_size]
        symbols = ",".join(
            ("sh" if code.startswith("6") else "sz") + code
            for code in batch
        )
        url = f"https://hq.sinajs.cn/list={symbols}"
        req = urllib.request.Request(url, headers=SINA_HEADERS)

        body = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
                    raw = resp.read()
                body = raw.decode("gbk", errors="ignore")
                break
            except Exception as exc:
                if attempt == 2:
                    print(f"[Quote] batch {start + 1}-{start + len(batch)} failed: {exc}")
                else:
                    time.sleep(1)

        if not body:
            continue

        for symbol, payload in re.findall(r'hq_str_([a-z0-9]+)="([^"]*)"', body, flags=re.I):
            fields = payload.split(",")
            if len(fields) < 4:
                continue
            code = symbol[2:]
            if not code:
                continue
            current_price = num(fields[3], 0)
            prev_close = num(fields[2], 0) if len(fields) > 2 else 0
            quote = {
                "name": fields[0] if fields else "",
                "price": current_price,
                "prev_close": prev_close,
                "date": fields[30] if len(fields) > 30 else "",
                "time": fields[31] if len(fields) > 31 else "",
            }
            quotes[code] = quote

        time.sleep(0.08)

    return quotes


def find_previous_prediction(scan_date):
    candidates = []
    for name in os.listdir(DATA_DIR):
        m = DATE_RE.match(name)
        if not m:
            continue
        date = m.group(1)
        if date < scan_date:
            candidates.append((date, os.path.join(DATA_DIR, name)))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    return candidates[0]


def pool_order(pool):
    return {
        "重点观察": 0,
        "预备池": 1,
        "观察池": 2,
        "淘汰": 3,
    }.get(pool, 9)


def pct_cell_value(value):
    if value is None:
        return "-"
    return (value / 100.0, 5, "number")


def build_validation_workbook(path, prediction_date, verification_date, rows_data, quotes):
    # Reuse the repository's existing XLSX writer so styles and formatting
    # remain consistent with the existing candidate-pool review workbook.
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from export_candidate_pool_excel import (
        build_xlsx,
        style_value,
        num_cell,
    )

    headers = [
        "原预测排名",
        "预测日期",
        "验证日期",
        "代码",
        "名称",
        "预测日收盘价",
        "验证日收盘价",
        "次日实际涨跌幅",
        "预测日涨跌幅",
        "候选池",
        "评级",
        "调整分",
        "P级",
        "三共振",
        "连板概率",
        "验证结果",
        "是否涨停",
        "是否跌停",
    ]

    rows = [[style_value(h, 1) for h in headers]]

    valid_returns = []
    result_counts = {"上涨": 0, "下跌": 0, "平盘": 0, "未获取": 0}
    limit_up_count = 0
    limit_down_count = 0

    for item in rows_data:
        code = str(item.get("code") or "")
        quote = quotes.get(code) or {}
        pred_price = num(item.get("price"), 0)
        close_price = num(quote.get("price"), 0)

        if pred_price > 0 and close_price > 0:
            actual_change = (close_price - pred_price) / pred_price * 100
            valid_returns.append(actual_change)
            if actual_change > 0.0001:
                result = "上涨"
                result_counts["上涨"] += 1
            elif actual_change < -0.0001:
                result = "下跌"
                result_counts["下跌"] += 1
            else:
                result = "平盘"
                result_counts["平盘"] += 1
            is_limit_up = actual_change >= 9.8
            is_limit_down = actual_change <= -9.8
            if is_limit_up:
                limit_up_count += 1
            if is_limit_down:
                limit_down_count += 1
        else:
            actual_change = None
            result = "未获取"
            result_counts["未获取"] += 1
            is_limit_up = False
            is_limit_down = False

        res = item.get("resonance") or {}
        rec = item.get("recency") or {}

        rows.append([
            num_cell(item.get("_rank"), 3),
            style_value(prediction_date, 2),
            style_value(verification_date, 2),
            style_value(code, 2),
            style_value(item.get("name"), 2),
            num_cell(pred_price, 4),
            num_cell(close_price, 4) if close_price > 0 else style_value("-", 2),
            pct_cell_value(actual_change),
            pct_cell_value(item.get("change_pct")),
            style_value(item.get("pool"), 2),
            style_value(item.get("grade"), 2),
            num_cell(item.get("adjusted_total"), 4),
            style_value("P" + text(rec.get("tier")), 2),
            style_value(f'{num(res.get("count"), 0):.0f}/3', 2),
            pct_cell_value(item.get("lianban_probability")),
            style_value(result, 2),
            style_value("是" if is_limit_up else "否", 2),
            style_value("是" if is_limit_down else "否", 2),
        ])

    avg_change = sum(valid_returns) / len(valid_returns) if valid_returns else None
    median_change = sorted(valid_returns)[len(valid_returns) // 2] if valid_returns else None
    win_rate = (
        sum(1 for x in valid_returns if x > 0) / len(valid_returns) * 100
        if valid_returns else None
    )

    summary = [
        [style_value("次日验证统计", 8), style_value("数值", 8)],
        [style_value("预测日期", 7), style_value(prediction_date, 2)],
        [style_value("验证日期", 7), style_value(verification_date, 2)],
        [style_value("预测股票数", 7), num_cell(len(rows_data), 3)],
        [style_value("成功获取行情", 7), num_cell(len(valid_returns), 3)],
        [style_value("平均次日涨跌幅", 7), pct_cell_value(avg_change)],
        [style_value("中位数次日涨跌幅", 7), pct_cell_value(median_change)],
        [style_value("上涨占比", 7), pct_cell_value(win_rate)],
        [style_value("上涨家数", 7), num_cell(result_counts["上涨"], 3)],
        [style_value("下跌家数", 7), num_cell(result_counts["下跌"], 3)],
        [style_value("平盘家数", 7), num_cell(result_counts["平盘"], 3)],
        [style_value("未获取行情", 7), num_cell(result_counts["未获取"], 3)],
        [style_value("次日涨停家数", 7), num_cell(limit_up_count, 3)],
        [style_value("次日跌停家数", 7), num_cell(limit_down_count, 3)],
        [],
        [style_value("按原预测排名统计", 8), style_value("平均次日涨跌幅", 8), style_value("上涨占比", 8)],
    ]

    for topn in (1, 3, 6, 10, 20):
        values = [
            (num(row.get("price"), 0), quotes.get(str(row.get("code") or ""), {}).get("price"))
            for row in rows_data[:topn]
        ]
        returns = [
            (cur - pred) / pred * 100
            for pred, cur in values
            if pred > 0 and num(cur, 0) > 0
        ]
        avg = sum(returns) / len(returns) if returns else None
        up = sum(1 for x in returns if x > 0) / len(returns) * 100 if returns else None
        summary.append([
            style_value(f"Top{topn}", 2),
            pct_cell_value(avg),
            pct_cell_value(up),
        ])

    summary.append([])
    summary.append([
        style_value("按候选池统计", 8),
        style_value("股票数", 8),
        style_value("平均次日涨跌幅", 8),
        style_value("上涨占比", 8),
    ])
    for pool in ("重点观察", "预备池", "观察池", "淘汰"):
        pool_rows = [r for r in rows_data if r.get("pool") == pool]
        pool_returns = []
        for r in pool_rows:
            pred = num(r.get("price"), 0)
            cur = num((quotes.get(str(r.get("code") or ""), {}) or {}).get("price"), 0)
            if pred > 0 and cur > 0:
                pool_returns.append((cur - pred) / pred * 100)
        pool_avg = sum(pool_returns) / len(pool_returns) if pool_returns else None
        pool_up = sum(1 for x in pool_returns if x > 0) / len(pool_returns) * 100 if pool_returns else None
        summary.append([
            style_value(pool, 2),
            num_cell(len(pool_rows), 3),
            pct_cell_value(pool_avg),
            pct_cell_value(pool_up),
        ])

    os.makedirs(os.path.dirname(path), exist_ok=True)
    build_xlsx(
        path,
        [
            (
                "次日验证",
                rows,
                [10, 12, 12, 10, 14, 13, 13, 14, 12, 12, 8, 10, 8, 9, 11, 10, 10, 10],
                f"R{len(rows)}",
            ),
            ("验证统计", summary, [22, 16, 18, 16], None),
        ],
    )


def main():
    now = datetime.now(timezone(timedelta(hours=8)))
    latest_path = os.path.join(DATA_DIR, "seven_factor_latest.json")
    if not os.path.exists(latest_path):
        raise SystemExit("seven_factor_latest.json not found; skip verification")

    today = load_json(latest_path)
    scan_date = str(today.get("scan_date") or now.strftime("%Y-%m-%d"))
    verification_date = scan_date
    current_candidates = today.get("candidates") or []
    if not current_candidates:
        raise SystemExit("today candidate pool is empty; refusing to create verification")

    prediction_date, prediction_path = find_previous_prediction(scan_date)
    if not prediction_path:
        print("[Verify] no previous prediction archive found; nothing to verify")
        return

    previous = load_json(prediction_path)
    candidates = list(previous.get("candidates") or [])
    if not candidates:
        print(f"[Verify] previous prediction {prediction_date} has no candidates; nothing to verify")
        return

    # Match the exact ranking rule used by the current prediction Excel.
    candidates.sort(
        key=lambda x: (
            pool_order(x.get("pool")),
            -num(x.get("adjusted_total")),
        )
    )
    for idx, row in enumerate(candidates, 1):
        row["_rank"] = idx

    print(f"[Verify] prediction date: {prediction_date}")
    print(f"[Verify] verification date: {verification_date}")
    print(f"[Verify] stocks to verify: {len(candidates)}")

    quotes = fetch_sina_quotes([r.get("code") for r in candidates])
    print(f"[Verify] quotes received: {len(quotes)}/{len(candidates)}")

    output = os.path.join(
        OUT_DIR,
        f"次日验证_{prediction_date}_vs_{verification_date}.xlsx",
    )
    build_validation_workbook(
        output,
        prediction_date,
        verification_date,
        candidates,
        quotes,
    )
    print(f"[Verify] exported: {output}")


if __name__ == "__main__":
    main()
