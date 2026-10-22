#!/usr/bin/env python3
"""Analyze accumulated next-day validation workbooks without changing the picker."""
import csv
import json
import math
import os
import re
import statistics
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VALID_DIR = DATA / "candidate_pool_validation"
REVIEW_DIR = DATA / "candidate_pool_reviews"
OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

VALID_RE = re.compile(r"次日验证_(\d{4}-\d{2}-\d{2})_vs_(\d{4}-\d{2}-\d{2})\.xlsx$")
REVIEW_RE = re.compile(r"候选池复盘_(\d{4}-\d{2}-\d{2})\.xlsx$")
FACTOR_KEYS = [
    "stock_recognition", "capital_preheat", "kline_chip",
    "theme_catalyst", "sector_strength", "market_cap_liquidity", "sentiment",
]
FACTOR_NAMES = {
    "stock_recognition": "个股辨识度",
    "capital_preheat": "资金预热",
    "kline_chip": "K线筹码",
    "theme_catalyst": "题材催化",
    "sector_strength": "板块强度",
    "market_cap_liquidity": "市值流动性",
    "sentiment": "情绪环境",
}
POOL_ORDER = {"重点观察": 0, "预备池": 1, "观察池": 2, "淘汰": 3}


def num(v, default=None):
    if v is None or v == "":
        return default
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def cell_pct(v):
    # Custom workbook writer stores percentage cells as decimal fractions.
    x = num(v)
    return None if x is None else x * 100.0


def txt(v):
    return "" if v is None else str(v).strip()


def read_sheet(path, preferred):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[preferred] if preferred in wb.sheetnames else wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        header = [txt(x) for x in next(rows, ())]
        out = []
        for values in rows:
            if not values or all(x is None for x in values):
                continue
            d = {header[i]: values[i] if i < len(values) else None for i in range(len(header))}
            if not any(v is not None for v in d.values()):
                continue
            out.append(d)
        return out, list(wb.sheetnames)
    finally:
        wb.close()


def read_review(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if "候选池" not in wb.sheetnames:
            return {}, {}
        ws = wb["候选池"]
        it = ws.iter_rows(values_only=True)
        header = [txt(x) for x in next(it, ())]
        stocks = {}
        for vals in it:
            if not vals or all(x is None for x in vals):
                continue
            d = {header[i]: vals[i] if i < len(header) else None for i in range(len(header))}
            code = txt(d.get("代码"))
            if code:
                stocks[code.zfill(6)] = {
                    "raw_score": num(d.get("原始分")),
                    "price": num(d.get("价格")),
                    "pred_day_pct": cell_pct(d.get("涨跌幅")),
                    "turnover_pct": cell_pct(d.get("换手率")),
                    "market_cap_yi": num(d.get("流通市值(亿)")),
                    "history_limit_up_count": num(d.get("历史涨停次数")),
                    "history_max_consecutive": num(d.get("最高连板")),
                    "days_since_last_lu": num(d.get("距上次涨停(日)")),
                    "review_pool": txt(d.get("候选池")),
                    "review_grade": txt(d.get("评级")),
                    "review_adjusted_score": num(d.get("调整分")),
                    "review_p_tier": txt(d.get("P级")),
                    "resonance_count": num(d.get("三共振")),
                    "turnover_cell": d.get("换手率"),
                }
        market = {}
        if "市场概览" in wb.sheetnames:
            ws2 = wb["市场概览"]
            for vals in ws2.iter_rows(values_only=True):
                if len(vals) >= 2 and vals[0] is not None:
                    k = txt(vals[0])
                    if k in {"情绪分", "情绪标签", "涨停数", "跌停数", "强势股数", "炸板率", "最高连板"}:
                        v = vals[1]
                        market[k] = cell_pct(v) if k == "炸板率" else (num(v) if k in {"情绪分", "涨停数", "跌停数", "强势股数", "最高连板"} else txt(v))
        return stocks, market
    finally:
        wb.close()


def read_factor_json(pred_date):
    path = DATA / f"seven_factor_{pred_date}.json"
    if not path.exists():
        return {}, {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        factors = {}
        for c in data.get("candidates") or []:
            code = txt(c.get("code")).zfill(6)
            scores = c.get("scores") or {}
            factors[code] = {
                **{k: num(scores.get(k)) for k in FACTOR_KEYS},
                "raw_score_json": num(scores.get("total")),
                "score_pool_json": txt(c.get("pool")),
                "grade_json": txt(c.get("grade")),
            }
        market = data.get("market_sentiment") or {}
        return factors, {
            "情绪分_json": num(market.get("sentiment_score")),
            "情绪标签_json": txt(market.get("sentiment_label")),
            "涨停数_json": num(market.get("limit_up_count")),
            "跌停数_json": num(market.get("limit_down_count")),
            "强势股数_json": num(market.get("strong_count")),
            "炸板率_json": num(market.get("explosion_rate")),
            "最高连板_json": num(market.get("max_boards_est")),
        }
    except Exception:
        return {}, {}


def p_tier(v):
    s = txt(v).upper()
    m = re.search(r"P\s*(\d)", s)
    return int(m.group(1)) if m else None


def actual_return(row):
    x = row.get("次日实际涨跌幅")
    if x is None:
        return None
    # XLSX stores this percentage cell as decimal fraction; after parser normalizes below
    return num(x)


def percentile(vals, q):
    if not vals:
        return None
    a = sorted(vals)
    pos = (len(a) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(a) - 1)
    return a[lo] + (a[hi] - a[lo]) * (pos - lo)


def base_metrics(rows):
    xs = [num(r.get("actual_return_pct")) for r in rows if num(r.get("actual_return_pct")) is not None]
    if not xs:
        return {"n": 0}
    wins = [x for x in xs if x > 0]
    losses = [x for x in xs if x < 0]
    dates = sorted({r.get("prediction_date") for r in rows if r.get("prediction_date")})
    per_day = defaultdict(list)
    for r in rows:
        x = num(r.get("actual_return_pct"))
        if x is not None:
            per_day[r["prediction_date"]].append(x)
    day_win = [sum(x > 0 for x in vals) / len(vals) * 100 for vals in per_day.values() if vals]
    day_mean = [statistics.mean(vals) for vals in per_day.values() if vals]
    return {
        "n": len(xs),
        "unique_stocks": len({r.get("code") for r in rows if num(r.get("actual_return_pct")) is not None}),
        "days": len(dates),
        "win_rate_pct": round(len(wins) / len(xs) * 100, 2),
        "avg_return_pct": round(statistics.mean(xs), 3),
        "median_return_pct": round(statistics.median(xs), 3),
        "p10_return_pct": round(percentile(xs, 0.10), 3),
        "p90_return_pct": round(percentile(xs, 0.90), 3),
        "avg_win_pct": round(statistics.mean(wins), 3) if wins else None,
        "avg_loss_pct": round(statistics.mean(losses), 3) if losses else None,
        "ge_2pct_pct": round(sum(x >= 2 for x in xs) / len(xs) * 100, 2),
        "le_minus_2pct_pct": round(sum(x <= -2 for x in xs) / len(xs) * 100, 2),
        "limit_up_pct": round(sum(x >= 9.8 for x in xs) / len(xs) * 100, 2),
        "limit_down_pct": round(sum(x <= -9.8 for x in xs) / len(xs) * 100, 2),
        "daily_avg_win_rate_pct": round(statistics.mean(day_win), 2) if day_win else None,
        "daily_avg_return_pct": round(statistics.mean(day_mean), 3) if day_mean else None,
    }


def group_report(rows, keyfun, order=None, min_n=1):
    groups = defaultdict(list)
    for r in rows:
        key = keyfun(r)
        if key is not None and key != "":
            groups[str(key)].append(r)
    out = []
    for key, vals in groups.items():
        m = base_metrics(vals)
        if m.get("n", 0) < min_n:
            continue
        m["group"] = key
        out.append(m)
    if order:
        out.sort(key=lambda x: order.index(x["group"]) if x["group"] in order else len(order))
    else:
        out.sort(key=lambda x: (-x.get("win_rate_pct", -1), -x.get("n", 0)))
    return out


def rank_avg(values):
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    k = 0
    while k < n:
        end = k + 1
        while end < n and values[order[end]] == values[order[k]]:
            end += 1
        rank = (k + end - 1) / 2 + 1
        for j in range(k, end):
            ranks[order[j]] = rank
        k = end
    return ranks


def corr(xs, ys, spearman=False):
    pairs = [(num(x), num(y)) for x, y in zip(xs, ys) if num(x) is not None and num(y) is not None]
    if len(pairs) < 3:
        return None
    x, y = zip(*pairs)
    x, y = list(x), list(y)
    if spearman:
        x, y = rank_avg(x), rank_avg(y)
    mx, my = statistics.mean(x), statistics.mean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return None
    return round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy), 4)


def top_n_report(rows, sort_field, method, ns=(1, 2, 3, 5, 10, 20)):
    by_day = defaultdict(list)
    for r in rows:
        if num(r.get("actual_return_pct")) is not None:
            by_day[r["prediction_date"]].append(r)
    result = []
    for n in ns:
        picked = []
        daily_means = []
        daily_win = []
        any_win_days = []
        all_win_days = []
        for date, vals in sorted(by_day.items()):
            eligible = [r for r in vals if num(r.get(sort_field)) is not None]
            if method == "P级优先":
                eligible.sort(key=lambda r: (
                    r.get("p_tier") if r.get("p_tier") is not None else 99,
                    -num(r.get("adjusted_score"), -1e9),
                    num(r.get("original_rank"), 1e9),
                ))
            elif sort_field == "original_rank":
                eligible.sort(key=lambda r: num(r.get("original_rank"), 1e9))
            else:
                eligible.sort(key=lambda r: (num(r.get(sort_field), -1e9), -num(r.get("original_rank"), 1e9)), reverse=True)
            selected = eligible[:n]
            returns = [num(r.get("actual_return_pct")) for r in selected if num(r.get("actual_return_pct")) is not None]
            if returns:
                picked.extend(selected)
                daily_means.append(statistics.mean(returns))
                daily_win.append(sum(x > 0 for x in returns) / len(returns) * 100)
                any_win_days.append(any(x > 0 for x in returns))
                all_win_days.append(all(x > 0 for x in returns))
        m = base_metrics(picked)
        m.update({
            "method": method, "top_n_per_day": n,
            "days_with_picks": len(daily_means),
            "daily_mean_selected_return_pct": round(statistics.mean(daily_means), 3) if daily_means else None,
            "daily_mean_selected_win_rate_pct": round(statistics.mean(daily_win), 2) if daily_win else None,
            "days_at_least_one_winner_pct": round(sum(any_win_days) / len(any_win_days) * 100, 2) if any_win_days else None,
            "days_all_picks_win_pct": round(sum(all_win_days) / len(all_win_days) * 100, 2) if all_win_days else None,
        })
        result.append(m)
    return result


def add_bins(row):
    def interval(x, cuts, labels):
        if x is None:
            return "缺失"
        for i, cut in enumerate(cuts):
            if x < cut:
                return labels[i]
        return labels[-1]
    s = num(row.get("adjusted_score"))
    row["score_bin"] = interval(s, [50, 60, 65, 70, 75], ["<50", "50-59.9", "60-64.9", "65-69.9", "70-74.9", ">=75"])
    p = num(row.get("pred_day_pct"))
    row["pred_day_pct_bin"] = interval(p, [-3, 0, 2, 5, 8], ["<-3%", "-3%~0%", "0%~2%", "2%~5%", "5%~8%", ">=8%"])
    t = num(row.get("turnover_pct"))
    row["turnover_bin"] = interval(t, [1, 3, 5, 10, 15], ["<1%", "1%~3%", "3%~5%", "5%~10%", "10%~15%", ">=15%"])
    c = num(row.get("market_cap_yi"))
    row["market_cap_bin"] = interval(c, [30, 50, 100, 200], ["<30亿", "30-49.9亿", "50-99.9亿", "100-199.9亿", ">=200亿"])
    h = num(row.get("history_limit_up_count"))
    row["history_lu_bin"] = interval(h, [1, 3, 6], ["0次", "1-2次", "3-5次", ">=6次"])
    d = num(row.get("days_since_last_lu"))
    row["days_since_lu_bin"] = interval(d, [1, 4, 11, 21], ["0天/当日", "1-3天", "4-10天", "11-20天", ">=21天"])
    r = txt(row.get("resonance"))
    m = re.search(r"(\d+)\s*/\s*3", r)
    row["resonance_bin"] = f"{m.group(1)}/3" if m else "缺失"


def compact_row(r):
    keys = [
        "prediction_date", "verification_date", "evaluation_eligible", "original_rank", "code", "name",
        "pred_close", "verify_close", "pool", "grade", "p_tier_label", "adjusted_score", "raw_score",
        "actual_return_pct", "pred_day_pct", "turnover_pct", "market_cap_yi",
        "resonance", "lianban_probability_pct", "history_limit_up_count",
        "history_max_consecutive", "days_since_last_lu",
        "market_sentiment_label", "limit_up_count_market", "limit_down_count_market",
    ] + FACTOR_KEYS
    return {k: r.get(k) for k in keys}


def main():
    validation_files = sorted(VALID_DIR.glob("次日验证_*.xlsx"))
    review_files = {m.group(1): p for p in REVIEW_DIR.glob("候选池复盘_*.xlsx") if (m := REVIEW_RE.match(p.name))}
    rows = []
    workbook_meta = []
    factor_json_dates = set()

    for path in validation_files:
        match = VALID_RE.match(path.name)
        if not match:
            continue
        pred_file_date, verify_file_date = match.groups()
        val_rows, sheets = read_sheet(path, "次日验证")
        review_map, market = ({}, {})
        review_path = review_files.get(pred_file_date)
        if review_path:
            review_map, market = read_review(review_path)
        factor_map, factor_market = read_factor_json(pred_file_date)
        if factor_map:
            factor_json_dates.add(pred_file_date)
        if factor_market:
            market = {**market, **{k.replace("_json", ""): v for k, v in factor_market.items() if v is not None}}
        valid_in_file = 0
        for vr in val_rows:
            code = txt(vr.get("代码")).zfill(6)
            act = cell_pct(vr.get("次日实际涨跌幅"))
            pred_date = txt(vr.get("预测日期")) or pred_file_date
            verify_date = txt(vr.get("验证日期")) or verify_file_date
            rev = review_map.get(code, {})
            fac = factor_map.get(code, {})
            row = {
                "prediction_date": pred_date, "verification_date": verify_date,
                "original_rank": num(vr.get("原预测排名")),
                "code": code, "name": txt(vr.get("名称")),
                "pred_close": num(vr.get("预测日收盘价")),
                "verify_close": num(vr.get("验证日收盘价")),
                "actual_return_pct": act,
                "pred_day_pct": cell_pct(vr.get("预测日涨跌幅")) if vr.get("预测日涨跌幅") is not None else rev.get("pred_day_pct"),
                "pool": txt(vr.get("候选池")) or rev.get("review_pool", ""),
                "grade": txt(vr.get("评级")) or rev.get("review_grade", ""),
                "adjusted_score": num(vr.get("调整分")) if vr.get("调整分") is not None else rev.get("review_adjusted_score"),
                "raw_score": rev.get("raw_score", fac.get("raw_score_json")),
                "p_tier_label": txt(vr.get("P级")) or rev.get("review_p_tier", ""),
                "p_tier": p_tier(vr.get("P级") or rev.get("review_p_tier")),
                "resonance": txt(vr.get("三共振")),
                "lianban_probability_pct": cell_pct(vr.get("连板概率")) if vr.get("连板概率") is not None else None,
                "turnover_pct": rev.get("turnover_pct"),
                "market_cap_yi": rev.get("market_cap_yi"),
                "history_limit_up_count": rev.get("history_limit_up_count"),
                "history_max_consecutive": rev.get("history_max_consecutive"),
                "days_since_last_lu": rev.get("days_since_last_lu"),
                "market_sentiment_label": txt(market.get("情绪标签") or market.get("情绪标签_json")),
                "market_sentiment_score": num(market.get("情绪分") if market.get("情绪分") is not None else market.get("情绪分_json")),
                "limit_up_count_market": num(market.get("涨停数") if market.get("涨停数") is not None else market.get("涨停数_json")),
                "limit_down_count_market": num(market.get("跌停数") if market.get("跌停数") is not None else market.get("跌停数_json")),
                "strong_count_market": num(market.get("强势股数") if market.get("强势股数") is not None else market.get("强势股数_json")),
                "explosion_rate_market_pct": num(market.get("炸板率") if market.get("炸板率") is not None else market.get("炸板率_json")),
                **{k: fac.get(k) for k in FACTOR_KEYS},
            }
            if row["actual_return_pct"] is not None:
                valid_in_file += 1
            add_bins(row)
            rows.append(row)
        workbook_meta.append({
            "file": path.name, "prediction_date": pred_file_date,
            "verification_date": verify_file_date, "sheet_names": sheets,
            "raw_rows": len(val_rows), "valid_return_rows": valid_in_file,
            "review_joined_rows": sum(1 for vr in val_rows if txt(vr.get("代码")).zfill(6) in review_map),
            "factor_json_joined_rows": sum(1 for vr in val_rows if txt(vr.get("代码")).zfill(6) in factor_map),
        })

    all_valid_rows = [r for r in rows if num(r.get("actual_return_pct")) is not None]
    if not all_valid_rows:
        raise SystemExit("No valid validation returns parsed.")

    all_dates = sorted({r["prediction_date"] for r in all_valid_rows})
    daily_quality = []
    excluded_dates = set()
    for date in all_dates:
        rs_all = [r for r in all_valid_rows if r["prediction_date"] == date]
        xs = [num(r.get("actual_return_pct")) for r in rs_all if num(r.get("actual_return_pct")) is not None]
        zero_n = sum(abs(x) < 1e-9 for x in xs)
        unchanged_n = sum(
            num(r.get("pred_close")) is not None and num(r.get("verify_close")) is not None
            and abs(num(r.get("pred_close")) - num(r.get("verify_close"))) < 1e-8
            for r in rs_all
        )
        zero_rate = zero_n / len(xs) * 100 if xs else 0
        unchanged_rate = unchanged_n / len(rs_all) * 100 if rs_all else 0
        likely_stale = bool(xs) and zero_rate >= 98 and max(abs(x) for x in xs) < 1e-8
        if likely_stale:
            excluded_dates.add(date)
        daily_quality.append({
            "prediction_date": date,
            "verification_date": min(r["verification_date"] for r in rs_all),
            "n": len(xs),
            "zero_return_rows": zero_n,
            "zero_return_rate_pct": round(zero_rate, 2),
            "unchanged_close_rows": unchanged_n,
            "unchanged_close_rate_pct": round(unchanged_rate, 2),
            "mean_abs_return_pct": round(statistics.mean(abs(x) for x in xs), 6) if xs else None,
            "excluded_from_signal_analysis": likely_stale,
            "reason": "次日所有样本涨跌幅均为0，疑似休市/行情未更新" if likely_stale else "",
        })
    valid_rows = [r for r in all_valid_rows if r["prediction_date"] not in excluded_dates]
    for r in all_valid_rows:
        r["evaluation_eligible"] = r["prediction_date"] not in excluded_dates
    if not valid_rows:
        raise SystemExit("No usable validation dates remain after excluding stale/closed-market snapshots.")
    dates = sorted({r["prediction_date"] for r in valid_rows})

    daily = []
    for date in dates:
        rs = [r for r in valid_rows if r["prediction_date"] == date]
        item = {"prediction_date": date, **base_metrics(rs)}
        item["market_sentiment_label"] = next((r["market_sentiment_label"] for r in rs if r.get("market_sentiment_label")), "")
        item["market_limit_up_count"] = next((r["limit_up_count_market"] for r in rs if r.get("limit_up_count_market") is not None), None)
        item["market_limit_down_count"] = next((r["limit_down_count_market"] for r in rs if r.get("limit_down_count_market") is not None), None)
        daily.append(item)

    # A small set of interpretable, pre-defined selection rules; top two per signal day.
    rules = [
        ("P1", lambda r: r.get("p_tier") == 1),
        ("P1-P2", lambda r: r.get("p_tier") in (1, 2)),
        ("评级A", lambda r: r.get("grade") == "A"),
        ("评级A/B", lambda r: r.get("grade") in ("A", "B")),
        ("调整分>=65", lambda r: num(r.get("adjusted_score"), -1e9) >= 65),
        ("调整分>=70", lambda r: num(r.get("adjusted_score"), -1e9) >= 70),
        ("三共振3/3", lambda r: r.get("resonance_bin") == "3/3"),
        ("P1/P2+评级A/B", lambda r: r.get("p_tier") in (1, 2) and r.get("grade") in ("A", "B")),
        ("P1/P2+评级A/B+三共振3/3", lambda r: r.get("p_tier") in (1, 2) and r.get("grade") in ("A", "B") and r.get("resonance_bin") == "3/3"),
        ("排除P4/P5", lambda r: r.get("p_tier") in (1, 2, 3)),
    ]
    rule_results = []
    for name, predicate in rules:
        selected = []
        daily_selected = []
        by_day = defaultdict(list)
        for r in valid_rows:
            if predicate(r):
                by_day[r["prediction_date"]].append(r)
        for date, vals in sorted(by_day.items()):
            vals.sort(key=lambda r: num(r.get("adjusted_score"), -1e9), reverse=True)
            daily_selected.extend(vals[:2])
            all_for_rule = vals
            daily_selected_returns = [num(r.get("actual_return_pct")) for r in vals[:2] if num(r.get("actual_return_pct")) is not None]
            if daily_selected_returns:
                selected.extend(vals[:2])
        mm = base_metrics(selected)
        mm.update({"rule": name, "top2_per_day_after_filter": True, "days_with_eligible_stocks": len(by_day), "avg_picks_per_day_all_days": round(len(selected) / len(dates), 2)})
        rule_results.append(mm)
    rule_results.sort(key=lambda x: (x.get("win_rate_pct", -1), x.get("avg_return_pct", -999)), reverse=True)

    tier_order = ["P1", "P2", "P3", "P4", "P5", "未知"]
    tier_rows = group_report(valid_rows, lambda r: r.get("p_tier_label") if r.get("p_tier") else "未知", tier_order)
    grade_rows = group_report(valid_rows, lambda r: r.get("grade") or "未知", ["A", "B", "C", "D", "未知"])
    tier_grade_rows = group_report(valid_rows, lambda r: (r.get("p_tier_label") or "未知") + " × " + (r.get("grade") or "未知"), min_n=10)
    pool_rows = group_report(valid_rows, lambda r: r.get("pool") or "未知", ["重点观察", "预备池", "观察池", "淘汰", "未知"])
    score_bins = group_report(valid_rows, lambda r: r.get("score_bin"), ["<50", "50-59.9", "60-64.9", "65-69.9", "70-74.9", ">=75", "缺失"])
    resonance_rows = group_report(valid_rows, lambda r: r.get("resonance_bin"), ["0/3", "1/3", "2/3", "3/3", "缺失"])
    pred_pct_rows = group_report(valid_rows, lambda r: r.get("pred_day_pct_bin"), ["<-3%", "-3%~0%", "0%~2%", "2%~5%", "5%~8%", ">=8%", "缺失"])
    turnover_rows = group_report(valid_rows, lambda r: r.get("turnover_bin"), ["<1%", "1%~3%", "3%~5%", "5%~10%", "10%~15%", ">=15%", "缺失"])
    mcap_rows = group_report(valid_rows, lambda r: r.get("market_cap_bin"), ["<30亿", "30-49.9亿", "50-99.9亿", "100-199.9亿", ">=200亿", "缺失"])
    history_lu_rows = group_report(valid_rows, lambda r: r.get("history_lu_bin"), ["0次", "1-2次", "3-5次", ">=6次", "缺失"])
    days_lu_rows = group_report(valid_rows, lambda r: r.get("days_since_lu_bin"), ["0天/当日", "1-3天", "4-10天", "11-20天", ">=21天", "缺失"])
    sentiment_rows = group_report(valid_rows, lambda r: r.get("market_sentiment_label") or "缺失", min_n=5)

    rank_compare = []
    rank_compare.extend(top_n_report(valid_rows, "original_rank", "验证表排序（候选池→分数）"))
    rank_compare.extend(top_n_report(valid_rows, "adjusted_score", "只按调整分"))
    rank_compare.extend(top_n_report(valid_rows, "adjusted_score", "P级优先"))
    if sum(1 for r in valid_rows if num(r.get("raw_score")) is not None) > 100:
        rank_compare.extend(top_n_report(valid_rows, "raw_score", "只按原始分"))

    component_results = []
    for key in FACTOR_KEYS:
        subset = [r for r in valid_rows if num(r.get(key)) is not None]
        if len(subset) < 30:
            continue
        vals = [num(r.get(key)) for r in subset]
        rets = [num(r.get("actual_return_pct")) for r in subset]
        row = {
            "factor": key, "label": FACTOR_NAMES.get(key, key), "n": len(subset),
            "pearson_with_next_day_return": corr(vals, rets),
            "spearman_with_next_day_return": corr(vals, rets, True),
        }
        # Factor quintiles are formed within the joined historical sample, for diagnosis only.
        ordered = sorted(subset, key=lambda r: num(r.get(key)))
        for i in range(5):
            lo = round(i * len(ordered) / 5)
            hi = round((i + 1) * len(ordered) / 5)
            row[f"Q{i+1}"] = base_metrics(ordered[lo:hi])
        component_results.append(row)

    method_by_day = {}
    for method, field in [("验证表排序（候选池→分数）", "original_rank"), ("只按调整分", "adjusted_score"), ("P级优先", "adjusted_score"), ("只按原始分", "raw_score")]:
        per_day = defaultdict(list)
        for r in valid_rows:
            if num(r.get(field)) is not None:
                per_day[r["prediction_date"]].append(r)
        best = []
        for date, vals in per_day.items():
            if method == "P级优先":
                vals.sort(key=lambda r: (
                    r.get("p_tier") if r.get("p_tier") is not None else 99,
                    -num(r.get("adjusted_score"), -1e9),
                    num(r.get("original_rank"), 1e9),
                ))
            elif field == "original_rank":
                vals.sort(key=lambda r: num(r.get(field), 1e9))
            else:
                vals.sort(key=lambda r: (num(r.get(field), -1e9), -num(r.get("original_rank"), 1e9)), reverse=True)
            if vals:
                best.append({"date": date, "code": vals[0]["code"], "name": vals[0]["name"], "actual_return_pct": vals[0]["actual_return_pct"]})
        method_by_day[method] = {
            "top1_picks": best,
            "top1_win_days_pct": round(sum(num(x["actual_return_pct"], -999) > 0 for x in best) / len(best) * 100, 2) if best else None,
            "top1_average_return_pct": round(statistics.mean([num(x["actual_return_pct"]) for x in best]), 3) if best else None,
        }

    report = {
        "title": "七因子候选池历史次日验证分析",
        "generated_from_branch": "analysis/candidate-pool-validation-20261022",
        "data_period": {"prediction_dates": [dates[0], dates[-1]], "verification_dates": [min(r["verification_date"] for r in valid_rows), max(r["verification_date"] for r in valid_rows)]},
        "coverage": {
            "validation_workbooks": len(workbook_meta), "prediction_days_all": len(all_dates),
            "prediction_days_used": len(dates), "quality_excluded_dates": sorted(excluded_dates),
            "raw_candidate_rows": len(rows), "valid_return_rows_all": len(all_valid_rows),
            "valid_return_rows_used": len(valid_rows),
            "unique_stocks_all": len({r["code"] for r in all_valid_rows}),
            "unique_stocks_used": len({r["code"] for r in valid_rows}),
            "review_join_rows": sum(x["review_joined_rows"] for x in workbook_meta),
            "factor_json_joined_rows": sum(x["factor_json_joined_rows"] for x in workbook_meta),
            "factor_json_prediction_dates": sorted(factor_json_dates),
            "files": workbook_meta,
        },
        "overall_raw_including_suspect_dates": base_metrics(all_valid_rows),
        "overall": base_metrics(valid_rows),
        "daily_data_quality": daily_quality,
        "daily_baseline": daily,
        "p_tier": tier_rows,
        "grade": grade_rows,
        "p_tier_x_grade": tier_grade_rows,
        "candidate_pool": pool_rows,
        "adjusted_score_bins": score_bins,
        "resonance": resonance_rows,
        "prediction_day_change_bins": pred_pct_rows,
        "turnover_bins": turnover_rows,
        "market_cap_bins": mcap_rows,
        "historical_limit_up_count_bins": history_lu_rows,
        "days_since_last_limit_up_bins": days_lu_rows,
        "market_sentiment_labels": sentiment_rows,
        "rank_methods_topn": rank_compare,
        "top1_method_summary": method_by_day,
        "factor_component_analysis": component_results,
        "predefined_filters_top2_per_day": rule_results,
        "excluded_prediction_dates": sorted(excluded_dates),
        "interpretation_cautions": [
            "样本为按预测日期重复出现的股票-日期记录，不能把同一股票跨日记录视为完全独立。",
            "分组胜率是描述性结果；规则是在同一批历史样本中比较，存在多重尝试/过拟合风险，需留出最近日期做样本外验证。",
            "该系统扫描时间为收盘后；预测日收盘价到验证日收盘价的收益不是可直接成交的真实买入收益，未计次日开盘跳空、滑点、手续费和买不到涨停等限制。",
            "市场情绪分组的独立样本单位是交易日，不是股票；交易日数量较少时只作提示，不能据此定论。"
        ],
    }

    (OUT_DIR / "validation_analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT_DIR / "validation_rows.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = list(compact_row(valid_rows[0]).keys())
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in all_valid_rows:
            writer.writerow(compact_row(row))

    md = []
    md.append("# 七因子候选池历史次日验证分析")
    md.append("")
    md.append(f"- 预测日期覆盖：{dates[0]} 至 {dates[-1]}，共 {len(dates)} 个预测日")
    md.append(f"- 验证工作簿：{len(workbook_meta)} 个；原始有效记录：{len(all_valid_rows):,}；剔除疑似休市/行情未更新日期 {len(excluded_dates)} 个后，有效记录：{len(valid_rows):,}。")
    md.append(f"- 剔除后上涨率：{report['overall'].get('win_rate_pct')}%；平均次日涨跌幅：{report['overall'].get('avg_return_pct')}%；中位数：{report['overall'].get('median_return_pct')}%。")
    md.append(f"- 未剔除异常日期时的上涨率/平均涨跌幅：{report['overall_raw_including_suspect_dates'].get('win_rate_pct')}% / {report['overall_raw_including_suspect_dates'].get('avg_return_pct')}%。")
    md.append("")
    md.append("## 数据质量检查")
    md.append("")
    md.append("| 预测日 | 验证日 | 样本数 | 次日涨跌幅为0的占比 | 收盘价未变占比 | 是否剔除 |")
    md.append("|---|---|---:|---:|---:|---|")
    for x in daily_quality:
        md.append(f"| {x['prediction_date']} | {x['verification_date']} | {x['n']} | {x['zero_return_rate_pct']}% | {x['unchanged_close_rate_pct']}% | {'是' if x['excluded_from_signal_analysis'] else '否'} |")
    md.append("")
    def table(title, items, cols):
        md.append(f"## {title}")
        md.append("")
        md.append("| " + " | ".join(cols) + " |")
        md.append("|" + "|".join(["---"] * len(cols)) + "|")
        for x in items:
            md.append("| " + " | ".join(str(x.get(c, "")) for c in cols) + " |")
        md.append("")
    table("P 级", tier_rows, ["group", "n", "days", "win_rate_pct", "avg_return_pct", "median_return_pct", "daily_avg_win_rate_pct", "limit_up_pct", "le_minus_2pct_pct"])
    table("评级", grade_rows, ["group", "n", "days", "win_rate_pct", "avg_return_pct", "median_return_pct", "daily_avg_win_rate_pct", "limit_up_pct", "le_minus_2pct_pct"])
    table("P 级 × 评级（样本量至少 10）", tier_grade_rows, ["group", "n", "days", "win_rate_pct", "avg_return_pct", "median_return_pct", "daily_avg_win_rate_pct"])
    table("候选池层级", pool_rows, ["group", "n", "days", "win_rate_pct", "avg_return_pct", "median_return_pct", "daily_avg_win_rate_pct"])
    table("调整分区间", score_bins, ["group", "n", "days", "win_rate_pct", "avg_return_pct", "median_return_pct", "daily_avg_win_rate_pct"])
    table("排序方式比较：每天按不同方法选 Top N", rank_compare, ["method", "top_n_per_day", "n", "win_rate_pct", "avg_return_pct", "daily_mean_selected_win_rate_pct", "daily_mean_selected_return_pct", "days_at_least_one_winner_pct", "days_all_picks_win_pct"])
    table("预设筛选规则：每天按调整分取前 2 只", rule_results, ["rule", "n", "days", "win_rate_pct", "avg_return_pct", "median_return_pct", "daily_avg_win_rate_pct", "avg_picks_per_day_all_days"])
    table("因子分项与次日收益", component_results, ["label", "n", "pearson_with_next_day_return", "spearman_with_next_day_return"])
    md.append("## 按预测日涨跌幅/换手率/历史涨停特征/三共振分组")
    for title, items in [
        ("预测日涨跌幅", pred_pct_rows), ("换手率", turnover_rows),
        ("历史涨停次数", history_lu_rows), ("距上次涨停", days_lu_rows),
        ("三共振", resonance_rows), ("流通市值", mcap_rows),
        ("市场情绪标签", sentiment_rows),
    ]:
        md.append(f"### {title}")
        md.append("")
        md.append("| 分组 | 样本数 | 覆盖天数 | 上涨率% | 平均涨跌幅% | 中位涨跌幅% | 日均上涨率% |")
        md.append("|---|---:|---:|---:|---:|---:|---:|")
        for x in items:
            md.append(f"| {x.get('group')} | {x.get('n')} | {x.get('days')} | {x.get('win_rate_pct')} | {x.get('avg_return_pct')} | {x.get('median_return_pct')} | {x.get('daily_avg_win_rate_pct')} |")
        md.append("")
    md.append("## 逐日全池基准")
    md.append("")
    md.append("undefined")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    for x in daily:
        md.append(f"| {x.get('prediction_date')} | {min([r['verification_date'] for r in valid_rows if r['prediction_date']==x['prediction_date']])} | {x.get('n')} | {x.get('win_rate_pct')} | {x.get('avg_return_pct')} | {x.get('p10_return_pct')} | {x.get('limit_up_pct')} | {x.get('limit_down_pct')} | {x.get('market_sentiment_label')} | {x.get('market_limit_up_count')} | {x.get('market_limit_down_count')} |")
    md.append("")
    md.append("## 解释边界")
    md.extend([f"- {x}" for x in report["interpretation_cautions"]])
    md.append("")
    md.append("原始分组明细及逐条记录见同目录 JSON/CSV。该脚本只读取历史数据，不修改评分器、预测名单或原始验证工作簿。")
    (OUT_DIR / "validation_analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "workbooks": len(workbook_meta), "prediction_days": len(dates),
        "raw_rows": len(rows), "valid_rows": len(valid_rows),
        "review_joined": report["coverage"]["review_join_rows"],
        "factor_json_rows": report["coverage"]["factor_json_joined_rows"],
        "overall_raw_including_suspect_dates": report["overall_raw_including_suspect_dates"],
        "overall": report["overall"], "daily_data_quality": daily_quality,
        "tier": tier_rows, "grade": grade_rows,
        "p_tier_x_grade": tier_grade_rows,
        "topn": rank_compare,
        "rule_results": rule_results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
