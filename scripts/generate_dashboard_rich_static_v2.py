#!/usr/bin/env python3
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
    except Exception:
        return default


def pct(value):
    return "{:+.1f}%".format(num(value))


def load(name):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def factor_html(stock):
    mapping = [
        ("辨识度", ["identity_score", "recognition_score"]),
        ("资金", ["capital_score", "fund_score"]),
        ("K线", ["kline_score", "technical_score"]),
        ("题材", ["theme_score", "topic_score"]),
        ("板块", ["sector_score"]),
        ("流动性", ["liquidity_score"]),
        ("情绪", ["emotion_score", "sentiment_score"]),
    ]
    parts = []
    for label, keys in mapping:
        value = None
        for key in keys:
            if stock.get(key) not in (None, ""):
                value = stock.get(key)
                break
        if value is not None:
            parts.append('<span class="factor"><b>{}</b> {}</span>'.format(esc(label), esc(value)))
    return "".join(parts) or '<span class="factor muted">七因子明细未单独存储</span>'


def row(index, stock):
    rec = stock.get("recency") or {}
    hist = stock.get("history") or {}
    res = stock.get("resonance") or {}
    watch = stock.get("next_day_watch") or []
    sector = stock.get("sector") or stock.get("sw_industry") or "-"
    watch_text = "；".join(str(x) for x in watch[:2]) if watch else "-"
    change_class = "up" if num(stock.get("change_pct")) >= 0 else "down"
    return (
        "<tr><td>{}</td>".format(index)
        + '<td><b>{}</b><small>{} · {}</small></td>'.format(esc(stock.get("name")), esc(stock.get("code")), esc(sector))
        + "<td>{}</td><td>P{}</td>".format(esc(stock.get("pool")), esc(rec.get("tier")))
        + '<td><b>{:.1f}</b><div class="factors">{}</div></td>'.format(num(stock.get("adjusted_total")), factor_html(stock))
        + '<td class="{}">{}</td>'.format(change_class, pct(stock.get("change_pct")))
        + "<td>{}%</td><td>{}%</td>".format(esc(stock.get("turnover_rate")), esc(stock.get("lianban_probability")))
        + "<td>{}</td><td>{}日</td><td>{}/3</td>".format(esc(hist.get("limit_up_count")), esc(hist.get("days_since_last_lu")), esc(res.get("count", 0)))
        + '<td class="watch">{}</td></tr>'.format(esc(watch_text))
    )


def news(items, empty):
    if not items:
        return '<div class="empty">{}</div>'.format(esc(empty))
    return "".join('<div class="news"><b>{}</b><small>{}</small></div>'.format(esc(x.get("title", "")), esc(x.get("pubDate", ""))) for x in items[:8])


def main():
    data = load("seven_factor_latest.json")
    evening = load("evening_latest.json")
    morning = load("morning_latest.json")
    candidates = list(data.get("candidates") or [])
    if not candidates:
        raise SystemExit("candidate pool empty")

    sentiment = data.get("market_sentiment") or {}
    score = num(sentiment.get("sentiment_score"), 50)
    if score < 40:
        action, desc = "谨慎观察", "市场偏弱，等待确认，不因为高分个股强行出手。"
    elif score < 55:
        action, desc = "轻仓试错", "市场偏弱，优先等待主线与资金确认。"
    elif score < 70:
        action, desc = "结构性参与", "围绕强板块挑核心，重点观察池优先。"
    else:
        action, desc = "积极参与", "市场进攻条件较好，优先主线核心与首板前候选。"

    ordered = sorted(candidates, key=lambda x: (int(num((x.get("recency") or {}).get("tier"), 99)), -num(x.get("adjusted_total"))))
    focus = [x for x in ordered if x.get("pool") == "重点观察"][:8]

    focus_html = []
    for i, stock in enumerate(focus, 1):
        rec = stock.get("recency") or {}
        hist = stock.get("history") or {}
        res = stock.get("resonance") or {}
        n = int(num(res.get("count"), 0))
        dots = "●" * n + "○" * max(0, 3 - n)
        focus_html.append(
            '<article class="focus"><div class="rank">TOP {}</div><b>{}</b><small>{} · {}</small>'
            '<strong>{:.1f}</strong><span class="pill">P{}</span><div class="facts">'
            '<span>三共振 {}</span><span>连板概率 {}%</span><span>涨幅 {}</span><span>换手 {}%</span>'
            '<span>历史涨停 {}</span><span>距上次 {}日</span></div></article>'.format(
                i,
                esc(stock.get("name")),
                esc(stock.get("code")),
                esc(stock.get("sector") or "未分类"),
                num(stock.get("adjusted_total")),
                esc(rec.get("tier", "-")),
                dots,
                esc(stock.get("lianban_probability")),
                pct(stock.get("change_pct")),
                esc(stock.get("turnover_rate")),
                esc(hist.get("limit_up_count")),
                esc(hist.get("days_since_last_lu")),
            )
        )

    sectors = sorted(data.get("sector_rankings") or [], key=lambda x: num(x.get("avg_change")), reverse=True)[:6]
    concepts = sorted(data.get("concept_rankings") or [], key=lambda x: num(x.get("avg_change")), reverse=True)[:10]
    sector_html = "".join('<div class="sector"><b>{}</b><strong>{}</strong><small>{}涨停 · {}强势</small></div>'.format(esc(x.get("name")), pct(x.get("avg_change")), esc(x.get("limit_up_count")), esc(x.get("strong_count"))) for x in sectors)
    concept_html = "".join('<span class="concept">#{} {} {}</span>'.format(esc(x.get("rank")), esc(x.get("name")), pct(x.get("avg_change"))) for x in concepts)
    rows = "".join(row(i, stock) for i, stock in enumerate(candidates, 1))

    css = """<style>
body{margin:0;background:#0a0d12;color:#e8eef7;font:14px Arial,"Microsoft YaHei",sans-serif}.wrap{max-width:1560px;margin:auto;padding:20px}.top{display:flex;justify-content:space-between}.title{font-size:28px;font-weight:800}.muted,small{color:#8792a4}section{margin-top:14px;padding:16px;background:#121720;border:1px solid #283241;border-radius:14px}.hero,.layout,.pipeline{display:grid;grid-template-columns:1.2fr 1fr;gap:14px}.card,.pipeline-card{padding:16px;background:#111821;border-radius:10px}.action{font-size:30px;font-weight:800}.metrics,.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}.metric,.stat{padding:10px;background:#0f141b;border-radius:8px}.metric span,.stat span{display:block;color:#8792a4;font-size:11px}.metric b,.stat b{display:block;font-size:18px}.focus-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.focus{padding:12px;background:#171e28;border:1px solid #283241;border-radius:10px}.rank{color:#f5c85b}.focus strong{float:right;font-size:22px}.pill{float:right;background:#202932;padding:4px 7px;border-radius:6px;font-size:10px}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}.facts span{padding:7px;background:#0f141b;border-radius:6px;font-size:10px}.sector{display:grid;grid-template-columns:1fr 80px 150px;gap:8px;padding:8px;background:#0f141b;border-radius:7px;margin-bottom:6px}.concepts{display:flex;flex-wrap:wrap;gap:6px}.concept{padding:7px 9px;background:#0f141b;border-radius:7px}.news{padding:8px 0;border-bottom:1px solid #222b36}.empty{padding:15px;text-align:center;color:#8792a4}.toolbar{display:flex;gap:8px;margin:10px 0}.toolbar input,.toolbar select,.toolbar button{background:#0f141b;border:1px solid #273140;color:#e8eef7;padding:8px;border-radius:7px}.table-wrap{max-height:780px;overflow:auto}.table{width:100%;min-width:1250px;border-collapse:collapse}.table th,.table td{padding:8px;border-bottom:1px solid #222b36;text-align:left;font-size:10px;vertical-align:top}.table th{position:sticky;top:0;background:#111821;color:#8792a4}.factor{display:inline-block;padding:3px 5px;margin:2px;background:#0f141b;border-radius:4px;color:#8792a4}.watch{max-width:240px;line-height:1.5}.up{color:#ff6575}.down{color:#35d09a}.footer{text-align:center;color:#5d6979;padding:20px;font-size:10px}@media(max-width:900px){.hero,.layout,.pipeline,.focus-grid{grid-template-columns:1fr}.metrics,.stats{grid-template-columns:1fr 1fr}.facts{grid-template-columns:1fr 1fr}}
</style>"""

    page = []
    page.append("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>七因子 · 决策仪表盘</title>")
    page.append(css)
    page.append("</head><body><div class='wrap'>")
    page.append('<div class="top"><div><div class="title">七因子 · 决策仪表盘</div><div class="muted">收盘选股 → 晚间预判 → 隔夜修正 → 竞价确认</div></div><div class="muted">扫描 {} {}<br>20:00：{} · 08:00：{}</div></div>'.format(esc(data.get("scan_date")), esc(data.get("scan_time")), "已生成" if evening else "尚未生成", "已生成" if morning else "尚未生成"))
    page.append('<section class="hero"><div class="card"><div class="muted">当前市场状态</div><div class="action">{}</div><div class="muted">情绪分 {:.1f}</div><p class="muted">{}</p></div><div class="card stats"><div class="stat"><span>重点观察</span><b>{}</b></div><div class="stat"><span>预备池</span><b>{}</b></div><div class="stat"><span>观察池</span><b>{}</b></div><div class="stat"><span>完整候选池</span><b>{}</b></div></div></section>'.format(action, score, desc, len(focus), sum(x.get("pool") == "预备池" for x in candidates), sum(x.get("pool") == "观察池" for x in candidates), len(candidates)))
    page.append('<section><h2>① 明日重点观察</h2><div class="focus-grid">{}</div></section>'.format("".join(focus_html)))
    page.append('<section><h2>② 主线与板块</h2><div class="layout"><div>{}</div><div class="concepts">{}</div></div></section>'.format(sector_html, concept_html))
    page.append('<section><h2>③ 晚间预判 / 隔夜修正</h2><div class="pipeline"><div class="pipeline-card"><h3>20:00 · 明日预判</h3>{}</div><div class="pipeline-card"><h3>08:00 · 隔夜修正</h3>{}</div></div></section>'.format(news(evening.get("headlines") or [], "等待20:00晚间信息更新。"), news(morning.get("overnight_headlines") or [], "等待08:00隔夜信息更新。")))
    page.append('<section><h2>④ 完整候选池 <span class="muted">{}只</span></h2><div class="toolbar"><input id="q" oninput="filterRows()" placeholder="搜索股票 / 代码 / 行业"><select id="pool" onchange="filterRows()"><option>全部</option><option>重点观察</option><option>预备池</option><option>观察池</option><option>淘汰</option></select><button onclick="sortScore()">按调整分排序</button></div><div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>股票 / 行业</th><th>池</th><th>P</th><th>调整分 / 七因子</th><th>涨幅</th><th>换手</th><th>连板概率</th><th>历史涨停</th><th>距上次</th><th>三共振</th><th>次日重点</th></tr></thead><tbody id="poolBody">{}</tbody></table></div></section>'.format(len(candidates), rows))
    page.append('<div class="footer">七因子决策系统 · 仅供研究参考，不构成投资建议</div></div>')
    page.append('''<script>function filterRows(){const q=(document.getElementById('q').value||'').toLowerCase(),p=document.getElementById('pool').value;for(const r of document.getElementById('poolBody').rows){const t=r.innerText.toLowerCase(),v=r.children[2].innerText;r.style.display=(p==='全部'||v===p)&&(!q||t.includes(q))?'':'none'}}function sortScore(){const b=document.getElementById('poolBody');[...b.rows].sort((a,c)=>(parseFloat(c.children[4].innerText)||0)-(parseFloat(a.children[4].innerText)||0)).forEach(r=>b.appendChild(r))}</script></body></html>''')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(page))
    print("generated rich static dashboard: {} candidates".format(len(candidates)))

if __name__ == "__main__":
    main()
