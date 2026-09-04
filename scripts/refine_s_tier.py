#!/usr/bin/env python3
"""在原七因子重点观察池之上做第二层 S 级筛选。

注意：本脚本不修改原七因子分数、候选池门槛、运行时间或一夜持股逻辑。
S级的唯一目的：在14:30左右扫描结果出来后，帮助人工优先检查“今天仍可交易、且最值得尾盘继续确认”的核心候选。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DATA_FILE = os.path.join(DATA_DIR, "seven_factor_latest.json")


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_s_eligible(row):
    """S级候选：直接从重点观察池二筛，不要求原A评级。"""
    if row.get("pool") != "重点观察":
        return False

    scores = row.get("scores") or {}
    recency = row.get("recency") or {}
    resonance = row.get("resonance") or {}

    # 1. 必须保留原模型的完整三共振，作为S级质量底线。
    if not resonance.get("all_three", False):
        return False

    # 2. S级需要高于重点观察入池线，但不再死卡78分。
    #    70分留出一定空间，让高质量但并非原A评级的股票也能进入人工二筛。
    if num(row.get("adjusted_total")) < 70:
        return False

    # 3. 三个最重要的“启动前”质量维度必须达到底线。
    if num(scores.get("stock_recognition")) < 16:
        return False
    if num(scores.get("capital_preheat")) < 12:
        return False
    if num(scores.get("kline_chip")) < 9:
        return False

    # 4. 题材 + 板块至少有一定共振，避免孤立个股进入S级。
    if num(scores.get("theme_catalyst")) + num(scores.get("sector_strength")) < 10:
        return False

    # 5. 流动性不能明显拖后腿。
    if num(scores.get("market_cap_liquidity")) < 7:
        return False

    # 6. 近期P4/P5优先级不适合“今天尾盘寻找新启动”，留给持续观察。
    #    P1/P2/P3仍可进入S，后续再由人工结合走势判断。
    if num(recency.get("tier"), 99) > 3:
        return False

    # 7. 当天已经涨停的股票不进入S：它已经没有尾盘买入空间。
    #    保留在原重点观察池/完整候选中，作为后续持续观察对象。
    if num(row.get("change_pct")) >= 9.8:
        return False
    if num(recency.get("current_streak")) >= 1:
        return False

    return True


def main():
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates") or []

    # 每次扫描都是全新 JSON，因此这里只负责本轮重新生成S级标记。
    s_rows = [row for row in candidates if is_s_eligible(row)]
    s_rows.sort(
        key=lambda row: (
            -num(row.get("adjusted_total")),
            -num((row.get("scores") or {}).get("capital_preheat")),
            -num((row.get("scores") or {}).get("stock_recognition")),
        )
    )
    s_rows = s_rows[:8]

    # 只清理/重建S标记，不修改原A/B/C/D评级。
    for row in candidates:
        row.pop("s_rank", None)
        row.pop("s_reason", None)
        row["s_tier"] = False

    for rank, row in enumerate(s_rows, 1):
        row["s_tier"] = True
        row["s_rank"] = rank
        row["s_reason"] = (
            "14:30尾盘二筛：重点观察池；三共振；调整分≥70；"
            "股性≥16；资金预热≥12；K线筹码≥9；题材+板块≥10；"
            "流动性≥7；P1-P3；当日未涨停且非当前连板"
        )
        watch = row.get("next_day_watch") or []
        row["next_day_watch"] = ["★S级：14:30优先人工筛选"] + [x for x in watch if x != "★S级：14:30优先人工筛选"]

    data["s_tier"] = {
        "name": "S级核心候选",
        "count": len(s_rows),
        "max_count": 8,
        "rule": "直接从重点观察池二筛；用于14:30后优先人工确认尾盘交易机会；不改原七因子分数，不要求原A评级；当天涨停/当前连板排除S但保留在候选池持续观察",
        "candidate_codes": [row.get("code") for row in s_rows],
        "excluded_from_s": {
            "today_limit_up": "当日涨停，今日无法尾盘买入，转持续观察",
            "current_streak": "当前连板，交易状态已不同于启动前候选，转持续观察",
            "recent_p4_p5": "近期刚涨停，暂不进入S级尾盘优先名单",
        },
    }

    summary = data.setdefault("summary", {})
    summary["s_tier_count"] = len(s_rows)

    # 保留原A/B/C/D统计，只新增S统计，避免S级影响原模型分级统计。
    grade_distribution = {"A": 0, "B": 0, "C": 0, "D": 0}
    for row in candidates:
        grade = row.get("grade", "D")
        if grade in grade_distribution:
            grade_distribution[grade] += 1
    summary["grade_distribution"] = grade_distribution

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    scan_date = data.get("scan_date")
    dated_file = os.path.join(DATA_DIR, f"seven_factor_{scan_date}.json")
    if scan_date and os.path.exists(dated_file):
        with open(dated_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"S级核心候选（14:30人工优先筛选）: {len(s_rows)} 只")
    for row in s_rows:
        print(
            f"  S{row['s_rank']} {row.get('code')} {row.get('name')} | "
            f"调整分:{num(row.get('adjusted_total')):.1f} | "
            f"P{row.get('recency', {}).get('tier', '-')} | "
            f"涨幅:{num(row.get('change_pct')):+.1f}% | "
            f"板块排名:{row.get('sector_rank', '-')}"
        )


if __name__ == "__main__":
    main()
