#!/usr/bin/env python3
"""在原七因子重点观察池之上做第二层 S 级筛选。

注意：本脚本不修改原七因子分数、候选池门槛、运行时间或一夜持股逻辑。
S 级只是在“重点观察 + A级”的基础上，用更严格的质量门槛进一步压缩人工复核范围。
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
    """S级硬门槛：只从原重点观察池中的A级候选继续筛选。"""
    if row.get("pool") != "重点观察":
        return False
    if row.get("grade") != "A":
        return False

    scores = row.get("scores") or {}
    recency = row.get("recency") or {}
    resonance = row.get("resonance") or {}

    # 1. 原模型整体强度：明显高于重点观察入池线
    if num(row.get("adjusted_total")) < 78:
        return False

    # 2. 原模型三大核心质量因子必须同时较强
    if num(scores.get("stock_recognition")) < 18:
        return False
    if num(scores.get("capital_preheat")) < 14:
        return False
    if num(scores.get("kline_chip")) < 10:
        return False

    # 3. 题材/板块不能只是“有分”，必须达到明显强势水平
    if num(scores.get("theme_catalyst")) + num(scores.get("sector_strength")) < 12:
        return False

    # 4. 流动性不能明显拖后腿
    if num(scores.get("market_cap_liquidity")) < 8:
        return False

    # 5. 三共振必须完整成立（A级本身已要求，这里再次显式约束，避免未来逻辑变化误放）
    if not resonance.get("all_three", False):
        return False

    # 6. 近期刚出现涨停/P5，不进入S级人工优先名单；允许P1/P2/P3继续观察
    if num(recency.get("tier"), 99) > 3:
        return False

    # 7. 至少处于其当前评分板块的前10名，避免孤立个股被整体分数误推高
    if num(row.get("sector_rank"), 999) > 10:
        return False

    return True


def main():
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates") or []

    # 每次扫描都是全新 JSON，因此这里只负责本轮重新生成 S 级标记。
    s_rows = [row for row in candidates if is_s_eligible(row)]
    s_rows.sort(key=lambda row: (-num(row.get("adjusted_total")), -num((row.get("scores") or {}).get("stock_recognition"))))

    # 人工尾盘时间有限：S级最多保留8只；不足8只则全部保留。
    s_rows = s_rows[:8]

    for row in candidates:
        # 将S视为A的更高一级，不改变原池归属。
        if row.get("grade") == "S":
            row["grade"] = "A"
        row.pop("s_rank", None)
        row.pop("s_reason", None)

    for rank, row in enumerate(s_rows, 1):
        row["grade"] = "S"
        row["s_rank"] = rank
        row["s_reason"] = (
            "严格二次筛选：重点观察+A；调整分≥78；股性≥18；资金预热≥14；"
            "K线筹码≥10；题材+板块≥12；流动性≥8；三共振；P1-P3；板块评分前10"
        )
        watch = row.get("next_day_watch") or []
        if not watch or watch[0] != "★S级核心候选":
            row["next_day_watch"] = ["★S级核心候选"] + [x for x in watch if x != "★S级核心候选"]

    data["s_tier"] = {
        "name": "S级核心候选",
        "count": len(s_rows),
        "max_count": 8,
        "rule": "仅从原重点观察池A级中二次筛选，不参与原七因子总分计算，不包含实时14:30后盯盘条件",
        "candidate_codes": [row.get("code") for row in s_rows],
    }

    summary = data.setdefault("summary", {})
    grade_distribution = summary.setdefault("grade_distribution", {})
    for g in ["A", "B", "C", "D", "S"]:
        grade_distribution[g] = 0
    for row in candidates:
        grade_distribution[row.get("grade", "D")] = grade_distribution.get(row.get("grade", "D"), 0) + 1
    summary["s_tier_count"] = len(s_rows)

    # 让后续页面/Excel直接读取最新 JSON 即可获得S级。
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    scan_date = data.get("scan_date")
    dated_file = os.path.join(DATA_DIR, f"seven_factor_{scan_date}.json")
    if scan_date and os.path.exists(dated_file):
        with open(dated_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"S级核心候选: {len(s_rows)} 只")
    for row in s_rows:
        print(
            f"  S{row['s_rank']} {row.get('code')} {row.get('name')} | "
            f"调整分:{num(row.get('adjusted_total')):.1f} | "
            f"P{row.get('recency', {}).get('tier', '-')} | "
            f"板块排名:{row.get('sector_rank', '-')}"
        )


if __name__ == "__main__":
    main()
