#!/usr/bin/env python3
"""Stable dashboard generator for the seven-factor scanner."""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "docs", "index.html")


def esc(value):
    return html.escape(str(value if value is not None else "-"))


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value):
    return f"{num(value):+.1f}%"


def cls(value):
    return "up" if num(value) >= 0 else "down"


def load_json(name, default=None):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return {} if default is None else default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def focus_card(stock, rank):
    rec = stock.get("recency") or {}
    res = stock.get("resonance") or {}
    hist = stock.get("history") or {}
    watch = stock.get("next_day_watch") or ["等待信号确认"]
    count = max(0, min(3, int(num(res.get("count"), 0))))
    dots = "●" * count + "○" * (3 - count)

    name = esc(stock.get("name"))
    code = esc(stock.get("code"))
    sector = esc(stock.get("sector", "未分类"))
    score = f"{num(stock.get('adjusted_total')):.1f}"
    tier = esc(rec.get("tier", "-"))
    probability = esc(stock.get("lianban_probability"))
    change_class = cls(stock.get("change_pct"))
    change = pct(stock.get("change_pct"))
    turnover = esc(stock.get("turnover_rate"))
    limit_up = esc(hist.get("limit_up_count"))
    days = esc(hist.get("days_since_last_lu"))
    first_watch = esc(watch[0] if watch else "等待信号确认")
    second_watch = esc(watch[1]) if len(watch) > 1 else "-"

    return (
        '<article class="focus">'
        f'<div class="rank">TOP {rank}</div>'
        '<div class="fmain">'
        f'<div><b>{name}</b><small>{code} · {sector}</small></div>'
        f'<strong>{score}</strong><span class="pill">P{tier}</span>'
        '</div>'
        '<div class="metrics">'
        f'<span>三共振 <b class="gold">{dots}</b></span>'
        f'<span>连板概率 <b>{probability}%</b></span>'
        f'<span>涨幅 <b class="{change_class}">{change}</b></span>'
        f'<span>换手 <b>{turnover}%</b></span>'
        f'<span>历史涨停 <b>{limit_up}</b></span>'
        f'<span>距上次 <b>{days}日</b></span>'
        '</div>'
        '<div class="watch">'
        '<b>次日重点</b>'
        f'<span>{first_watch}</span><span>{second_watch}</span>'
        '</div>'
        '</article>'
    )


def candidate_rows(candidates):
    rows = []
    for index, stock in enumerate(candidates, 1):
        rec = stock.get("recency") or {}
        res = stock.get("resonance") or {}
        sector = stock.get("sector") or "-"
        name = stock.get("name") or "-"
        code = stock.get("code") or "-"
        pool = stock.get("pool") or "-"
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><b>{esc(name)}</b><br><small>{esc(code)} · {esc(sector)}</small></td>"
            f"<td>{esc(pool)}</td>"
            f"<td>P{esc(rec.get('tier', '-'))}</td>"
            f"<td>{num(stock.get('adjusted_total')):.1f}</td>"
            f"<td class=\"{cls(stock.get('change_pct'))}\">{pct(stock.get('change_pct'))}</td>"
            f"<td>{esc(res.get('count', 0))}/3</td>"
            "</tr>"
        )
    return "".join(rows)


def build_page(data):
    sentiment = data.get("market_sentiment") or {}
    candidates = list(data.get("candidates") or [])
    ordered = sorted(
        candidates,
        key=lambda row: (
            int(num((row.get("recency") or {}).get("tier"), 99)),
            -num(row.get("adjusted_total")),
        ),
    )
    focus = [row for row in ordered if row.get("pool") == "重点观察"][:8]

    sectors = sorted(
        data.get("sector_rankings") or [],
        key=lambda row: num(row.get("avg_change")),
        reverse=True,
    )[:6]
    concepts = sorted(
        data.get("concept_rankings") or [],
        key=lambda row: num(row.get("avg_change")),
        reverse=True,
    )[:10]

    sentiment_score = num(sentiment.get("sentiment_score"), 50)
    if sentiment_score < 40:
        action = "谨慎观察"
        action_desc = "市场偏弱，等待确认，不因为个股高分强行出手"
    elif sentiment_score < 55:
        action = "轻仓试错"
        action_desc = "市场偏弱，优先等待主线与资金确认"
    elif sentiment_score < 70:
        action = "结构性参与"
        action_desc = "围绕强板块挑核心，重点观察池优先"
    else:
        action = "积极参与"
        action_desc = "市场进攻条件较好，优先主线核心与首板前候选"

    sector_html = "".join(
        f'<div class="sector"><b>{esc(row.get("name"))}</b>'
        f'<strong class="{cls(row.get("avg_change"))}">{pct(row.get("avg_change"))}</strong>'
        f'<small>{esc(row.get("limit_up_count"))}涨停 · {esc(row.get("strong_count"))}强势</small></div>'
        for row in sectors
    ) or '<div class="empty">暂无行业数据</div>'

    concept_html = "".join(
        f'<span class="concept">#{esc(row.get("rank"))} {esc(row.get("name"))} '
        f'<em class="{cls(row.get("avg_change"))}">{pct(row.get("avg_change"))}</em></span>'
        for row in concepts
    ) or '<div class="empty">暂无概念数据</div>'

    focus_html = "".join(focus_card(row, i) for i, row in enumerate(focus, 1))
    if not focus_html:
        focus_html = '<div class="empty">暂无重点观察股票</div>'

    rows_html = candidate_rows(candidates)

    css = """
<style>
:root{--bg:#0a0d12;--p:#121720;--p2:#171e28;--l:#283241;--t:#e8eef7;--m:#8792a4;--up:#ff6575;--down:#35d09a;--gold:#f5c85b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1480px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:20px}.title{font-size:27px;font-weight:900}.muted,small,.meta{color:var(--m)}.meta{text-align:right;font-size:11px;line-height:1.8}
.hero,.layout{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-top:14px}.box,.section{background:var(--p);border:1px solid var(--l);border-radius:15px}.box{padding:18px}.action{font-size:29px;font-weight:900}.metrics,.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.stats{grid-template-columns:1fr 1fr;padding:18px}
.metric,.stat{padding:10px;background:#10151d;border:1px solid #222c38;border-radius:9px}.metric span,.stat span{display:block;color:var(--m);font-size:10px}.metric b,.stat b{display:block;margin-top:4px;font-size:17px}.stat b{font-size:25px}.up{color:var(--up)}.down{color:var(--down)}.gold{color:var(--gold)}
.section{padding:16px;margin-top:14px}.focus-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.focus{background:var(--p2);border:1px solid var(--l);border-radius:12px;padding:13px}.rank{font-size:10px;color:var(--gold)}
.fmain{display:grid;grid-template-columns:1fr 80px 45px;gap:8px;align-items:center;margin-top:5px}.fmain b{font-size:15px}.fmain small{display:block;font-size:9px;margin-top:3px}.fmain>strong{font-size:21px;text-align:right}.pill{display:inline-flex;padding:4px 7px;border-radius:6px;background:#202932;color:#c8d3e2;font-size:9px}
.metrics{grid-template-columns:repeat(6,1fr);margin:11px 0}.metrics span{background:#10151d;border:1px solid #212b37;border-radius:7px;padding:7px;color:var(--m);font-size:9px}.metrics b{display:block;color:var(--t);margin-top:3px}.watch{display:flex;gap:8px;background:#0f141b;border-radius:7px;padding:8px;font-size:10px}.watch span{color:var(--m)}
.sector{display:grid;grid-template-columns:1fr 70px 120px;gap:8px;padding:9px 10px;background:#10151d;border:1px solid #212b37;border-radius:8px;margin-bottom:7px}.concepts{display:flex;flex-wrap:wrap;gap:7px}.concept{padding:8px 9px;background:#10151d;border:1px solid #212b37;border-radius:8px;font-size:10px}.concept em{font-style:normal;margin-left:6px}
.empty{padding:18px;text-align:center;color:var(--m);background:#0f141b;border-radius:8px}.pool-tools{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.pool-tools input,.pool-tools select{background:#0f141b;border:1px solid #273140;color:var(--t);padding:8px;border-radius:8px}.table-wrap{max-height:700px;overflow:auto}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:8px;border-bottom:1px solid #222b36;text-align:left;font-size:10px}.table th{color:var(--m)}
.footer{text-align:center;color:#5d6979;font-size:10px;padding:18px}
@media(max-width:1000px){.hero,.layout{grid-template-columns:1fr}.focus-grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(3,1fr)}}
@media(max-width:620px){.wrap{padding:12px}.top{align-items:flex-start;flex-direction:column}.meta{text-align:left}.metrics,.stats{grid-template-columns:repeat(2,1fr)}.metrics{grid-template-columns:1fr 1fr}.sector{grid-template-columns:1fr 60px}.sector small{display:none}}
</style>
"""

    js = """
<script>
function filterPool(){
  const q=(document.getElementById('q').value||'').toLowerCase();
  const p=document.getElementById('pool').value;
  for(const tr of document.getElementById('poolBody').rows){
    const text=tr.innerText.toLowerCase();
    tr.style.display=(p==='全部'||text.includes(p))&&(!q||text.includes(q))?'':'none';
  }
}
</script>
"""

    scan_date = esc(data.get("scan_date"))
    scan_time = esc(data.get("scan_time"))
    focus_count = len(focus)
    ready_count = sum(row.get("pool") == "预备池" for row in candidates)
    watch_count = sum(row.get("pool") == "观察池" for row in candidates)

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>七因子 · 决策仪表盘</title>{css}</head>
<body><div class="wrap">
<div class="top"><div><div class="title">七因子 · 决策仪表盘</div><div class="muted">收盘选股 → 晚间预判 → 隔夜修正 → 竞价确认</div></div>
<div class="meta">扫描 {scan_date} {scan_time}</div></div>
<section class="hero"><div class="box"><div class="muted">当前市场状态</div><div class="action">{esc(action)}</div>
<div class="muted">情绪分 {sentiment_score:.1f} · {esc(sentiment.get('sentiment_label','正常'))}</div><p class="muted">{esc(action_desc)}</p>
<div class="metrics"><div class="metric"><span>涨停</span><b class="up">{esc(sentiment.get('limit_up_count'))}</b></div>
<div class="metric"><span>跌停</span><b class="down">{esc(sentiment.get('limit_down_count'))}</b></div>
<div class="metric"><span>最高连板</span><b>{esc(sentiment.get('max_boards_est'))}</b></div>
<div class="metric"><span>炸板率</span><b>{esc(sentiment.get('explosion_rate'))}%</b></div></div></div>
<div class="box stats"><div class="stat"><span>重点观察</span><b>{focus_count}</b></div><div class="stat"><span>预备池</span><b>{ready_count}</b></div><div class="stat"><span>观察池</span><b>{watch_count}</b></div><div class="stat"><span>完整候选池</span><b>{len(candidates)}</b></div></div></section>
<section class="section"><h2>① 明日重点观察</h2><p class="muted">先看重点池，再看完整候选池</p><div class="focus-grid">{focus_html}</div></section>
<section class="section"><h2>② 主线与板块</h2><div class="layout"><div>{sector_html}</div><div class="concepts">{concept_html}</div></div></section>
<section class="section full-candidate-section"><h2>③ 完整候选池</h2><p class="muted">{len(candidates)}只 · 页面内完整保留</p>
<div class="pool-tools"><input id="q" oninput="filterPool()" placeholder="搜索股票 / 代码 / 板块"><select id="pool" onchange="filterPool()"><option>全部</option><option>重点观察</option><option>预备池</option><option>观察池</option><option>淘汰</option></select></div>
<div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>股票</th><th>池</th><th>P</th><th>调整分</th><th>涨幅</th><th>三共振</th></tr></thead>
<tbody id="poolBody">{rows_html}</tbody></table></div></section>
<div class="footer">七因子决策系统 · 仅供研究参考，不构成投资建议</div></div>{js}</body></html>"""


def main():
    data = load_json("seven_factor_latest.json")
    if not data.get("candidates"):
        raise RuntimeError("candidate pool is empty; refusing to overwrite dashboard")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    page = build_page(data)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"Dashboard generated: {OUT}")


if __name__ == "__main__":
    main()
