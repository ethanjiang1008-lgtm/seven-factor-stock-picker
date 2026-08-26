#!/usr/bin/env python3
"""Replace the dashboard's lazy candidate section with a static full candidate table."""
import json
import os
import re
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "seven_factor_latest.json")
OUT = os.path.join(ROOT, "docs", "index.html")

def esc(v):
    return html.escape(str(v if v is not None else "-"))

def num(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d

def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    candidates = data.get("candidates") or []
    if not candidates:
        raise SystemExit("candidate pool empty; refusing to alter dashboard")

    rows = []
    for i, r in enumerate(candidates, 1):
        rec = r.get("recency") or {}
        res = r.get("resonance") or {}
        change = num(r.get("change_pct"))
        cls = "up" if change >= 0 else "down"
        rows.append(
            f'<tr><td>{i}</td>'
            f'<td><b>{esc(r.get("name"))}</b><br><span class="muted">{esc(r.get("code"))} · {esc(r.get("sector") or r.get("sw_industry"))}</span></td>'
            f'<td>{esc(r.get("pool"))}</td>'
            f'<td>P{esc(rec.get("tier"))}</td>'
            f'<td>{num(r.get("adjusted_total")):.1f}</td>'
            f'<td class="{cls}">{change:+.1f}%</td>'
            f'<td>{esc(res.get("count", 0))}/3</td></tr>'
        )

    section = (
        '<section class="section full-candidate-section">'
        '<div style="display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap">'
        '<div><h2>④ 完整候选池</h2>'
        f'<p class="muted">完整展示全部 {len(candidates)} 只候选股，不再折叠、不依赖浏览器加载。</p></div>'
        '</div>'
        '<div class="toolbar-static">'
        '<span class="mini">全部</span><span class="mini">可直接浏览</span>'
        '</div>'
        '<div style="overflow:auto;max-height:72vh;border:1px solid #222c38;border-radius:10px">'
        '<table class="table"><thead><tr><th>#</th><th>股票</th><th>池</th><th>P</th><th>调整分</th><th>涨幅</th><th>三共振</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table></div></section>'
    )

    with open(OUT, encoding="utf-8") as f:
        page = f.read()

    start = page.find('<section class="section"><div class="toggle"')
    if start < 0:
        start = page.find('<section class="section"><div class="toggle"')
    if start < 0:
        raise SystemExit("could not locate lazy candidate section")
    end = page.find('</section>', start)
    if end < 0:
        raise SystemExit("could not locate end of candidate section")
    end += len('</section>')

    page = page[:start] + section + page[end:]
    page = page.replace('let loaded=false,all=[];', 'let loaded=true,all=[];')
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f"[force_full_candidate_section] wrote {len(candidates)} candidates into docs/index.html")

if __name__ == '__main__':
    main()
