#!/usr/bin/env python3
"""Replace the dashboard candidate section with a permanently expanded, information-rich table."""
import json
import os
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


def text_list(v):
    if isinstance(v, list):
        return [str(x) for x in v if x not in (None, "")]
    if v in (None, ""):
        return []
    return [str(v)]


def factor_summary(r):
    """Show available factor-level details when present, while remaining schema-tolerant."""
    candidates = [r.get("factor_scores"), r.get("factors"), r.get("factor_detail"), r.get("factor_details")]
    obj = next((x for x in candidates if isinstance(x, dict)), None)
    if not obj:
        return '<span class="muted">七因子汇总见调整分</span>'

    aliases = {
        "个股辨识度": ["个股辨识度", "recognition", "identity"],
        "资金预热": ["资金预热", "funds", "capital"],
        "K线筹码": ["K线筹码", "kline", "chip"],
        "题材催化": ["题材催化", "catalyst", "theme"],
        "板块强度": ["板块强度", "sector"],
        "市值流动性": ["市值流动性", "liquidity", "market_cap"],
        "情绪环境": ["情绪环境", "sentiment"],
    }
    bits = []
    for label, keys in aliases.items():
        found = None
        for k in keys:
            if k in obj:
                found = obj[k]
                break
        if isinstance(found, dict):
            found = found.get("score", found.get("value"))
        if found is not None:
            bits.append(f'<span class="factor-badge">{esc(label)} {esc(found)}</span>')
    return ''.join(bits) or '<span class="muted">七因子汇总见调整分</span>'


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
        hist = r.get("history") or {}
        change = num(r.get("change_pct"))
        cls = "up" if change >= 0 else "down"
        watch = text_list(r.get("next_day_watch"))
        watch_html = " / ".join(esc(x) for x in watch[:2]) or "-"
        sector = r.get("sector") or r.get("sw_industry") or "-"
        probability = r.get("lianban_probability")
        probability_html = f"{esc(probability)}%" if probability not in (None, "") else "-"
        turnover = r.get("turnover_rate")
        turnover_html = f"{esc(turnover)}%" if turnover not in (None, "") else "-"
        lu_count = hist.get("limit_up_count", r.get("limit_up_count"))
        days_since = hist.get("days_since_last_lu", r.get("days_since_last_lu"))
        factors = factor_summary(r)
        rows.append(
            f'<tr>'
            f'<td>{i}</td>'
            f'<td class="stock"><b>{esc(r.get("name"))}</b><br><small>{esc(r.get("code"))} · {esc(sector)}</small></td>'
            f'<td>{esc(r.get("pool"))}</td>'
            f'<td>P{esc(rec.get("tier"))}</td>'
            f'<td><b>{num(r.get("adjusted_total")):.1f}</b><div class="factor-mini">{factors}</div></td>'
            f'<td class="{cls}">{change:+.1f}%</td>'
            f'<td>{turnover_html}</td>'
            f'<td>{probability_html}</td>'
            f'<td>{esc(lu_count) if lu_count not in (None, "") else "-"}</td>'
            f'<td>{esc(days_since) + "日" if days_since not in (None, "") else "-"}</td>'
            f'<td>{esc(res.get("count", 0))}/3</td>'
            f'<td class="watch-cell">{watch_html}</td>'
            f'</tr>'
        )

    section = (
        '<section class="section full-candidate-section">'
        '<div style="display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap">'
        '<div><h2>④ 完整候选池</h2>'
        f'<p class="muted">完整展示全部 {len(candidates)} 只候选股，不折叠。每只股票恢复关键交易与历史信息。</p></div>'
        '<div class="toolbar-static"><span class="mini">全部展开</span><span class="mini">可搜索/筛选</span></div>'
        '</div>'
        '<div class="toolbar-static">'
        '<input id="richQ" placeholder="搜索股票 / 代码 / 行业 / 关注点" oninput="richFilter()">'
        '<select id="richPool" onchange="richFilter()"><option>全部</option><option>重点观察</option><option>预备池</option><option>观察池</option><option>淘汰</option></select>'
        '</div>'
        '<div style="overflow:auto;max-height:72vh;border:1px solid #222c38;border-radius:10px">'
        '<table class="table rich-table"><thead><tr>'
        '<th>#</th><th>股票 / 行业</th><th>池</th><th>P</th><th>调整分 / 因子</th><th>涨幅</th><th>换手</th><th>连板概率</th><th>历史涨停</th><th>距上次</th><th>三共振</th><th>次日关注</th>'
        '</tr></thead><tbody id="richBody">' + ''.join(rows) + '</tbody></table></div></section>'
    )

    with open(OUT, encoding="utf-8") as f:
        page = f.read()

    start = page.find('<section class="section"><div class="toggle"')
    if start < 0:
        start = page.find('<section class="section full-candidate-section">')
    if start < 0:
        raise SystemExit("could not locate candidate section")
    end = page.find('</section>', start)
    if end < 0:
        raise SystemExit("could not locate end of candidate section")
    end += len('</section>')

    page = page[:start] + section + page[end:]

    extra_css = '''<style>
.toolbar-static{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.toolbar-static input,.toolbar-static select{background:#0f141b;border:1px solid #273140;color:#e8eef7;padding:8px;border-radius:8px}.rich-table{min-width:1380px}.rich-table th,.rich-table td{vertical-align:top}.stock b{font-size:11px}.factor-mini{display:flex;flex-wrap:wrap;gap:3px;margin-top:5px}.factor-badge{display:inline-block;background:#101820;border:1px solid #26313e;border-radius:5px;padding:2px 4px;font-size:8px;color:#aeb9c8}.watch-cell{min-width:190px;line-height:1.55}
</style>'''
    page = page.replace('</head>', extra_css + '</head>', 1)

    filter_js = '''<script>
function richFilter(){const q=(document.getElementById('richQ').value||'').toLowerCase(),p=document.getElementById('richPool').value;for(const tr of document.getElementById('richBody').rows){const t=tr.innerText.toLowerCase();tr.style.display=(p==='全部'||t.includes(p))&&(!q||t.includes(q))?'':'none'}}
</script>'''
    page = page.replace('</body>', filter_js + '</body>', 1)

    with open(OUT, 'w', encoding="utf-8") as f:
        f.write(page)
    print(f"[force_full_candidate_section] wrote rich table for {len(candidates)} candidates into docs/index.html")


if __name__ == '__main__':
    main()
