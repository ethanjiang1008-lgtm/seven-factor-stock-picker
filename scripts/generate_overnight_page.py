#!/usr/bin/env python3
"""Generate a standalone page for the 20:00 and 08:00 analysis layers.

This script intentionally does NOT touch docs/index.html.
It reads data/evening_latest.json and data/morning_latest.json and writes
only docs/overnight.html.
"""
import html
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "docs", "overnight.html")
EVENING = os.path.join(DATA, "evening_latest.json")
MORNING = os.path.join(DATA, "morning_latest.json")


def esc(value):
    return html.escape(str(value if value is not None else "-"))


def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def fmt_time(value):
    if not value:
        return "尚未生成"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def safe_list(value):
    return value if isinstance(value, list) else []


def render_candidate(card):
    return (
        '<article class="candidate">'
        f'<div class="candidate-main"><strong>{esc(card.get("name"))}</strong>'
        f'<span>{esc(card.get("code"))}</span></div>'
        f'<div class="candidate-meta"><b>{esc(card.get("score"))}</b>'
        f'<span>{esc(card.get("pool"))}</span>'
        f'<span>{esc(card.get("tier"))}</span>'
        f'<span>{esc(card.get("sector"))}</span></div>'
        '</article>'
    )


def render_sector(row):
    return (
        '<div class="sector-row">'
        f'<span>{esc(row.get("name"))}</span>'
        f'<b>{float(row.get("avg_change", 0) or 0):+.2f}%</b>'
        f'<small>{esc(row.get("limit_up_count"))} 涨停 · {esc(row.get("strong_count"))} 强势</small>'
        '</div>'
    )


def render_news(item):
    return (
        '<div class="news-item">'
        f'<b>{esc(item.get("title"))}</b>'
        f'<small>{esc(item.get("pubDate"))}</small>'
        '</div>'
    )


def render():
    evening = load(EVENING)
    morning = load(MORNING)

    evening_candidates = safe_list(evening.get("focus_candidates"))
    evening_sectors = safe_list(evening.get("top_sectors"))
    evening_news = safe_list(evening.get("headlines"))

    morning_candidates = safe_list(morning.get("focus_candidates"))
    morning_news = safe_list(morning.get("overnight_headlines"))
    checks = morning.get("market_checks") or {}
    rules = safe_list(morning.get("adjustment_rules"))

    same_focus = set((x.get("code"), x.get("name")) for x in evening_candidates) & set(
        (x.get("code"), x.get("name")) for x in morning_candidates
    )

    evening_candidate_html = "".join(render_candidate(x) for x in evening_candidates[:10])
    if not evening_candidate_html:
        evening_candidate_html = '<div class="empty">等待 20:00 明日预判生成</div>'

    morning_candidate_html = "".join(render_candidate(x) for x in morning_candidates[:10])
    if not morning_candidate_html:
        morning_candidate_html = '<div class="empty">等待 08:00 隔夜修正生成</div>'

    sector_html = "".join(render_sector(x) for x in evening_sectors[:8]) or '<div class="empty">暂无板块数据</div>'
    evening_news_html = "".join(render_news(x) for x in evening_news[:12]) or '<div class="empty">暂无晚间消息</div>'
    morning_news_html = "".join(render_news(x) for x in morning_news[:15]) or '<div class="empty">暂无隔夜消息</div>'

    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    morning_ready = bool(morning)

    css = """
<style>
:root{--bg:#0a0d12;--panel:#121720;--panel2:#171e28;--line:#283241;--text:#e8eef7;--muted:#8792a4;--accent:#f5c85b;--good:#35d09a;--bad:#ff6575;--blue:#7fb1ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}.wrap{max-width:1480px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.title{font-size:28px;font-weight:900}.sub{margin-top:7px;color:var(--muted)}.meta{color:var(--muted);font-size:11px;line-height:1.8;text-align:right}.timeline{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}.stage{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}.stage h2{margin:0 0 6px;font-size:18px}.stage .time{color:var(--accent);font-size:12px;margin-bottom:14px}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px;margin-top:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}.card h3{margin:0 0 12px;font-size:15px}.candidate{padding:11px 0;border-bottom:1px solid #222b36}.candidate:last-child{border-bottom:0}.candidate-main{display:flex;justify-content:space-between;gap:10px}.candidate-main strong{font-size:14px}.candidate-main span{font-family:monospace;color:var(--blue);font-size:12px}.candidate-meta{display:flex;gap:8px;align-items:center;margin-top:6px;flex-wrap:wrap;color:var(--muted);font-size:11px}.candidate-meta b{color:var(--text);font-size:16px}.candidate-meta span{background:#1d2530;padding:3px 6px;border-radius:5px}.sector-row{display:grid;grid-template-columns:1fr 80px 150px;gap:8px;padding:9px 0;border-bottom:1px solid #222b36;align-items:center}.sector-row b{color:var(--good);text-align:right}.sector-row small{color:var(--muted);text-align:right}.news-item{padding:8px 0;border-bottom:1px solid #222b36}.news-item b{display:block;font-size:11px;line-height:1.5}.news-item small{display:block;color:var(--muted);font-size:9px;margin-top:3px}.check{padding:10px 11px;background:#10151d;border:1px solid #222c38;border-radius:9px;margin-bottom:8px}.check span{display:block;color:var(--muted);font-size:10px}.check b{display:block;margin-top:4px;font-size:13px}.rule{padding:8px 10px;margin-bottom:7px;border-left:3px solid var(--accent);background:#10151d;color:#c9d3df;font-size:11px;line-height:1.5}.badge{display:inline-flex;padding:4px 8px;border-radius:6px;background:#202932;color:#c8d3e2;font-size:10px;margin-right:6px}.empty{padding:22px;text-align:center;color:var(--muted);background:#0f141b;border-radius:8px}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:10px}.comparison .box{background:#10151d;border:1px solid #222c38;border-radius:10px;padding:12px}.comparison .box strong{display:block;font-size:21px}.comparison .box span{display:block;color:var(--muted);font-size:10px;margin-top:4px}.footer{text-align:center;color:#5d6979;font-size:10px;padding:20px}.nav{display:inline-block;margin-top:12px;color:var(--blue);font-size:12px;text-decoration:none}.nav:hover{text-decoration:underline}@media(max-width:900px){.timeline,.grid{grid-template-columns:1fr}.meta{text-align:left}.top{flex-direction:column}.sector-row{grid-template-columns:1fr 70px}.sector-row small{display:none}}
</style>
"""

    html_doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七因子 · 夜间分析中心</title>{css}</head>
<body><div class="wrap">
<div class="top"><div><div class="title">七因子 · 夜间分析中心</div><div class="sub">20:00 明日预判 → 08:00 隔夜修正 → 09:25 竞价确认</div><a class="nav" href="./index.html">返回收盘决策仪表盘 →</a></div>
<div class="meta">页面生成：{esc(generated_at)}<br>20:00：{esc(fmt_time(evening.get('generated_at')))}<br>08:00：{esc(fmt_time(morning.get('generated_at')))}</div></div>

<div class="timeline">
<section class="stage"><h2>20:00 · 明日预判</h2><div class="time">来源：收盘扫描结果 + 晚间新闻</div>
<div><span class="badge">重点候选 {len(evening_candidates)} 只</span><span class="badge">热门板块 {len(evening_sectors)} 个</span><span class="badge">新闻 {len(evening_news)} 条</span></div></section>
<section class="stage"><h2>08:00 · 隔夜修正</h2><div class="time">来源：20:00 预判 + 隔夜新闻</div>
<div><span class="badge">状态：{'已生成' if morning_ready else '尚未生成'}</span><span class="badge">重点候选 {len(morning_candidates)} 只</span><span class="badge">隔夜消息 {len(morning_news)} 条</span></div></section>
</div>

<div class="grid">
<section class="card"><h3>20:00 · 明日重点候选</h3>{evening_candidate_html}</section>
<section class="card"><h3>20:00 · 热门板块</h3>{sector_html}</section>
</div>

<div class="grid">
<section class="card"><h3>08:00 · 隔夜修正后的重点候选</h3>{morning_candidate_html}</section>
<section class="card"><h3>08:00 · 市场检查</h3>
<div class="check"><span>美股</span><b>{esc(checks.get('us_market','等待08:00更新'))}</b></div>
<div class="check"><span>大宗商品</span><b>{esc(checks.get('commodities','等待08:00更新'))}</b></div>
<div class="check"><span>政策 / 产业</span><b>{esc(checks.get('policy_and_industry','等待08:00更新'))}</b></div>
</section>
</div>

<section class="card" style="margin-top:14px"><h3>20:00 → 08:00 · 重点候选连续性</h3>
<div class="comparison"><div class="box"><strong>{len(evening_candidates)}</strong><span>20:00 重点候选</span></div><div class="box"><strong>{len(morning_candidates)}</strong><span>08:00 修正后候选</span></div><div class="box"><strong>{len(same_focus)}</strong><span>两次均保留</span></div><div class="box"><strong>{max(0, len(evening_candidates)-len(same_focus))}</strong><span>20:00 后未继续保留</span></div></div>
</section>

<div class="grid">
<section class="card"><h3>08:00 · 修正规则</h3>{''.join(f'<div class="rule">{esc(x)}</div>' for x in rules) or '<div class="empty">等待 08:00 修正规则</div>'}</section>
<section class="card"><h3>20:00 · 晚间信息</h3>{evening_news_html}</section>
</div>

<section class="card" style="margin-top:14px"><h3>08:00 · 隔夜信息</h3>{morning_news_html}</section>

<div class="footer">本页面只展示 20:00 / 08:00 分析层结果，不修改七因子评分，也不修改收盘决策页面。</div>
</div></body></html>"""
    return html_doc


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(render())
    print(f"[Overnight] generated {OUT}")


if __name__ == "__main__":
    main()
