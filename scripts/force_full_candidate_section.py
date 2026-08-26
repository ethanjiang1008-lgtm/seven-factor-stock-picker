#!/usr/bin/env python3
"""Replace the dashboard candidate section with the 8e4302d-style dense table."""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "seven_factor_latest.json")
OUT = os.path.join(ROOT, "docs", "index.html")


def esc(v):
    return html.escape(str(v if v is not None else "-"))


def pct(v):
    try:
        return f"{float(v):+.1f}%"
    except Exception:
        return esc(v)


def pct_cls(v):
    try:
        return "up" if float(v) >= 0 else "down"
    except Exception:
        return ""


def pool_badge(pool):
    colors = {"重点观察":"#e74c3c", "预备池":"#e67e22", "观察池":"#3498db", "淘汰":"#95a5a6"}
    return f'<span class="candidate-badge" style="background:{colors.get(pool, "#95a5a6")}">{esc(pool)}</span>'


def tier_badge(label, tag):
    colors = {"P1":"#27ae60", "P2":"#2980b9", "P3":"#f39c12", "P4":"#e67e22", "P5":"#e74c3c"}
    color = colors.get(label, "#7f8c8d")
    return f'<span class="candidate-tier" style="border-color:{color};color:{color}">{esc(label)} {esc(tag)}</span>'


def resonance(count):
    try:
        count = max(0, min(3, int(count or 0)))
    except Exception:
        count = 0
    return f'<span class="candidate-resonance">{"●"*count}{"○"*(3-count)}</span> {count}/3'


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    candidates = data.get("candidates") or []
    if not candidates:
        raise SystemExit("candidate pool empty; refusing to alter dashboard")

    order = {"重点观察":0, "预备池":1, "观察池":2, "淘汰":3}
    ranked = sorted(candidates, key=lambda r: (order.get(r.get("pool"), 9), -float(r.get("adjusted_total", 0) or 0)))
    rows = []
    for r in ranked:
        hist = r.get("history") or {}
        rec = r.get("recency") or {}
        res = r.get("resonance") or {}
        score = float(r.get("adjusted_total", 0) or 0)
        bar_color = "#e74c3c" if score >= 65 else "#e67e22" if score >= 60 else "#3498db" if score >= 50 else "#95a5a6"
        tags = "".join(f'<span class="candidate-watch-tag">{esc(t)}</span>' for t in (r.get("next_day_watch") or []))
        rows.append(
            '<tr>'
            f'<td class="candidate-code">{esc(r.get("code"))}</td>'
            f'<td class="candidate-name">{esc(r.get("name"))}</td>'
            f'<td>{esc(r.get("sector") or "-")}</td>'
            f'<td>{esc(r.get("price"))}</td>'
            f'<td class="{pct_cls(r.get("change_pct"))}">{pct(r.get("change_pct"))}</td>'
            f'<td>{esc(r.get("turnover_rate"))}%</td>'
            f'<td>{esc(r.get("circ_mcap_yi"))}</td>'
            f'<td class="candidate-score"><b>{esc(r.get("adjusted_total"))}</b><span class="candidate-score-bar"><i style="width:{max(0,min(100,score)):.0f}%;background:{bar_color}"></i></span><small>原{esc((r.get("scores") or {}).get("total"))}</small></td>'
            f'<td>{tier_badge(rec.get("tier_label", ""), rec.get("tag", ""))}</td>'
            f'<td>{pool_badge(r.get("pool", "-"))}</td>'
            f'<td class="grade-{esc(r.get("grade", "")).lower()}">{esc(r.get("grade"))}</td>'
            f'<td>{resonance(res.get("count"))}</td>'
            f'<td>{esc(r.get("lianban_probability"))}%</td>'
            f'<td>{esc(hist.get("limit_up_count"))}次/{esc(hist.get("max_consecutive"))}连</td>'
            f'<td>{esc(hist.get("days_since_last_lu"))}日</td>'
            f'<td class="candidate-watch">{tags}</td>'
            '</tr>'
        )

    section = (
        '<section class="section full-candidate-section">'
        '<div class="candidate-head">'
        '<div><div class="candidate-title">完整候选池</div>'
        f'<div class="muted">{len(ranked)} 只 · 恢复 8e4302d 的高信息密度横向表格</div></div>'
        '</div>'
        '<div class="candidate-table-wrap"><table class="candidate-table"><thead><tr>'
        '<th>代码</th><th>名称</th><th>行业</th><th>价格</th><th>涨跌幅</th><th>换手率</th><th>流通市值</th><th>调整分 / 原始分</th><th>P级</th><th>候选池</th><th>评级</th><th>三共振</th><th>连板概率</th><th>历史涨停</th><th>距上次</th><th>次日重点</th>'
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
        '</section>'
    )

    with open(OUT, encoding="utf-8") as f:
        page = f.read()

    start = page.find('<section class="section full-candidate-section">')
    if start < 0:
        start = page.find('<section class="section"><div class="toggle"')
    if start < 0:
        raise SystemExit("could not locate candidate section")
    end = page.find('</section>', start)
    if end < 0:
        raise SystemExit("could not locate end of candidate section")
    end += len('</section>')
    page = page[:start] + section + page[end:]

    css = '''<style>
.candidate-head{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap}.candidate-title{font-size:16px;font-weight:800;color:#fff}.candidate-table-wrap{overflow:auto;max-height:75vh;margin-top:12px;border:1px solid #293140;border-radius:10px}.candidate-table{width:100%;min-width:1450px;border-collapse:collapse;font-size:12px}.candidate-table th{position:sticky;top:0;z-index:2;background:#1a202b;color:#8590a3;padding:8px 6px;text-align:center;white-space:nowrap}.candidate-table td{padding:7px 6px;border-bottom:1px solid #222b36;text-align:center;white-space:nowrap;vertical-align:middle}.candidate-table td:first-child{text-align:left}.candidate-table tr:hover{background:#181e27}.candidate-code{font-family:monospace;color:#7fb1ff}.candidate-name{font-weight:700;color:#fff}.candidate-score{text-align:left!important;min-width:150px}.candidate-score>b{font-size:14px}.candidate-score-bar{width:60px;height:5px;background:#333;border-radius:3px;display:inline-block;margin:0 6px;vertical-align:middle}.candidate-score-bar i{display:block;height:100%;border-radius:3px}.candidate-score small{color:#697586;font-size:10px}.candidate-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;color:#fff}.candidate-tier{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;border:1px solid;white-space:nowrap}.grade-a{color:#ff6575;font-weight:700}.grade-b{color:#ffb15f;font-weight:700}.grade-c{color:#7fb1ff;font-weight:700}.grade-d{color:#8792a4}.candidate-resonance{color:#f6c453;letter-spacing:1px}.candidate-watch{white-space:normal!important;text-align:left!important;max-width:240px}.candidate-watch-tag{display:inline-block;background:#1d2430;border:1px solid #2a3443;border-radius:4px;padding:1px 6px;font-size:10px;margin:1px;color:#b7c5d8}
</style>'''
    if 'candidate-table-wrap' not in page:
        page = page.replace('</head>', css + '</head>', 1)

    with open(OUT, 'w', encoding="utf-8") as f:
        f.write(page)
    print(f"[force_full_candidate_section] restored 8e4302d-style candidate table for {len(ranked)} candidates")


if __name__ == '__main__': main()
