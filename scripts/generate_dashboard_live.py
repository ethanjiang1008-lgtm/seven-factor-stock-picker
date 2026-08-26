#!/usr/bin/env python3
"""Decision dashboard that auto-loads the full candidate pool on page load."""
import html, json, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,'data'); OUT=os.path.join(ROOT,'docs','index.html')
BASE='/seven-factor-stock-picker/'

def esc(v): return html.escape(str(v if v is not None else '-'))

def load(name):
    p=os.path.join(DATA,name)
    try:
        with open(p,encoding='utf-8') as f:return json.load(f)
    except Exception:return {}

def num(v,d=0):
    try:return float(v)
    except:return d

def action(score):
    s=num(score,50)
    if s<40:return '谨慎观察','市场偏弱，等待确认，不因为高分个股强行出手'
    if s<55:return '轻仓试错','市场偏弱，优先等待主线与资金确认'
    if s<70:return '结构性参与','围绕强板块挑核心，重点观察池优先'
    return '积极参与','市场进攻条件较好，优先主线核心与首板前候选'

def main():
    d=load('seven_factor_latest.json'); e=load('evening_latest.json'); m=load('morning_latest.json')
    if not d.get('candidates'): raise SystemExit('candidate pool empty; refuse to overwrite dashboard')
    s=d.get('market_sentiment') or {}; act,desc=action(s.get('sentiment_score'))
    focus=sorted([x for x in d['candidates'] if x.get('pool')=='重点观察'], key=lambda x:-num(x.get('adjusted_total')))[:8]
    secs=sorted(d.get('sector_rankings') or [], key=lambda x:num(x.get('avg_change')), reverse=True)[:6]
    cons=sorted(d.get('concept_rankings') or [], key=lambda x:num(x.get('avg_change')), reverse=True)[:10]
    ef=(e.get('focus_candidates') or [])[:8]
    meta=f"扫描 {esc(d.get('scan_date'))} {esc(d.get('scan_time'))} · 七因子评分独立"
    focus_html=''.join(f'''<article class="focus"><div class="rank">TOP {i}</div><div class="fmain"><div><b>{esc(r.get('name'))}</b><small>{esc(r.get('code'))} · {esc(r.get('sector','未分类'))}</small></div><strong>{num(r.get('adjusted_total')):.1f}</strong><span class="pill">P{esc((r.get('recency') or {}).get('tier','-'))}</span></div><div class="fm"><span>三共振 <b>{'●'*int(num((r.get('resonance') or {}).get('count')))+'○'*max(0,3-int(num((r.get('resonance') or {}).get('count'))))}</b></span><span>连板概率 <b>{esc(r.get('lianban_probability'))}%</b></span><span>涨幅 <b>{num(r.get('change_pct')):+.1f}%</b></span><span>换手 <b>{esc(r.get('turnover_rate'))}%</b></span></div><div class="watch"><b>次日重点</b><span>{esc((r.get('next_day_watch') or ['等待信号确认'])[0])}</span></div></article>''' for i,r in enumerate(focus,1))
    sec_html=''.join(f'<div class="sector"><b>{esc(x.get("name"))}</b><strong>{num(x.get("avg_change")):+.1f}%</strong><small>{esc(x.get("limit_up_count"))}涨停 · {esc(x.get("strong_count"))}强势</small></div>' for x in secs)
    con_html=''.join(f'<span class="concept">#{esc(x.get("rank"))} {esc(x.get("name"))} <em>{num(x.get("avg_change")):+.1f}%</em></span>' for x in cons)
    html_page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七因子 · 决策仪表盘</title><style>
:root{{--bg:#0a0d12;--p:#121720;--p2:#171e28;--l:#283241;--t:#e8eef7;--m:#8792a4;--up:#ff6575;--down:#35d09a;--gold:#f5c85b}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--t);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}.wrap{{max-width:1480px;margin:auto;padding:22px}}.top{{display:flex;justify-content:space-between;gap:20px}}.title{{font-size:27px;font-weight:900}}.muted,small,.meta{{color:var(--m)}}.meta{{text-align:right;font-size:11px;line-height:1.8}}section{{background:var(--p);border:1px solid var(--l);border-radius:15px;padding:16px;margin-top:14px}}.hero,.layout,.pipeline{{display:grid;grid-template-columns:1.2fr 1fr;gap:14px}}.hero .card,.pipeline-card{{background:#111821;border:1px solid #263241;border-radius:12px;padding:18px}}.action{{font-size:29px;font-weight:900}}.metrics,.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}}.metric,.stat{{padding:10px;background:#10151d;border:1px solid #222c38;border-radius:9px}}.metric span,.stat span{{display:block;color:var(--m);font-size:10px}}.metric b,.stat b{{display:block;margin-top:4px;font-size:17px}}.stat b{{font-size:25px}}.up{{color:var(--up)}}.down{{color:var(--down)}}.gold{{color:var(--gold)}}.focus-grid{{display:grid;grid-template-columns:1fr 1fr;gap:9px}}.focus{{background:var(--p2);border:1px solid var(--l);border-radius:12px;padding:13px}}.rank{{font-size:10px;color:var(--gold)}}.fmain{{display:grid;grid-template-columns:1fr 70px 42px;gap:8px;align-items:center;margin-top:5px}}.fmain b{{font-size:15px}}.fmain small{{display:block;font-size:9px;margin-top:3px}}.fmain>strong{{font-size:21px;text-align:right}}.pill,.mini{{display:inline-flex;padding:4px 7px;border-radius:6px;background:#202932;color:#c8d3e2;font-size:9px}}.fm{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:11px 0}}.fm span{{background:#10151d;border:1px solid #212b37;border-radius:7px;padding:7px;color:var(--m);font-size:9px}}.fm b{{display:block;color:var(--t);margin-top:3px}}.watch{{display:flex;gap:8px;background:#0f141b;border-radius:7px;padding:8px;font-size:10px}}.watch span{{color:var(--m)}}.sector{{display:grid;grid-template-columns:1fr 70px 130px;gap:8px;padding:9px 10px;background:#10151d;border:1px solid #212b37;border-radius:8px;margin-bottom:7px}}.concepts{{display:flex;flex-wrap:wrap;gap:7px}}.concept{{padding:8px 9px;background:#10151d;border:1px solid #212b37;border-radius:8px;font-size:10px}}.concept em{{font-style:normal;margin-left:6px;color:var(--up)}}.news{{padding:8px 0;border-bottom:1px solid #222b36}}.news b{{display:block;font-size:10px}}.news small{{font-size:9px}}.empty{{padding:18px;text-align:center;color:var(--m);background:#0f141b;border-radius:8px}}.toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}.toolbar input,.toolbar select{{background:#0f141b;border:1px solid #273140;color:var(--t);padding:8px;border-radius:8px}}.table{{width:100%;border-collapse:collapse}}.table th,.table td{{padding:8px;border-bottom:1px solid #222b36;text-align:left;font-size:10px}}.table th{{color:var(--m)}}.table-wrap{{max-height:760px;overflow:auto;border:1px solid #222c38;border-radius:10px}}.footer{{text-align:center;color:#5d6979;font-size:10px;padding:18px}}@media(max-width:1000px){{.hero,.layout,.pipeline{{grid-template-columns:1fr}}.focus-grid{{grid-template-columns:1fr}}}}@media(max-width:650px){{.wrap{{padding:12px}}.top{{flex-direction:column}}.meta{{text-align:left}}.metrics,.stats{{grid-template-columns:1fr 1fr}}.fm{{grid-template-columns:1fr 1fr}}.sector{{grid-template-columns:1fr 60px}}.sector small{{display:none}}}}
</style></head><body><div class="wrap"><div class="top"><div><div class="title">七因子 · 决策仪表盘</div><div class="muted">收盘选股 → 晚间预判 → 隔夜修正 → 竞价确认</div></div><div class="meta">{meta}<br>20:00：{'已生成' if e else '尚未生成'}<br>08:00：{'已生成' if m else '尚未生成'}</div></div>
<section class="hero"><div class="card"><div class="muted">当前市场状态</div><div class="action">{esc(act)}</div><div class="muted">情绪分 {num(s.get('sentiment_score')):.1f} · {esc(s.get('sentiment_label','正常'))}</div><p class="muted">{esc(desc)}</p><div class="metrics"><div class="metric"><span>涨停</span><b class="up">{esc(s.get('limit_up_count'))}</b></div><div class="metric"><span>跌停</span><b class="down">{esc(s.get('limit_down_count'))}</b></div><div class="metric"><span>最高连板</span><b>{esc(s.get('max_boards_est'))}</b></div><div class="metric"><span>炸板率</span><b>{esc(s.get('explosion_rate'))}%</b></div></div></div><div class="card stats"><div class="stat"><span>重点观察</span><b>8</b></div><div class="stat"><span>预备池</span><b>67</b></div><div class="stat"><span>观察池</span><b>189</b></div><div class="stat"><span>完整候选池</span><b>自动加载</b><small>页面打开即展示</small></div></div></section>
<section><h2>① 明日重点观察</h2><p class="muted">七因子负责选股；这里看优先级与证据</p><div class="focus-grid">{focus_html}</div></section>
<section><h2>② 主线与板块</h2><div class="layout"><div>{sec_html}</div><div class="concepts">{con_html}</div></div></section>
<section><h2>③ 晚间预判 / 隔夜修正</h2><div class="pipeline"><div class="pipeline-card"><h3>20:00 · 明日预判</h3>{''.join(f'<div class="news"><b>{esc(x.get("title",""))}</b><small>{esc(x.get("pubDate",""))}</small></div>' for x in (e.get('headlines') or [])[:8]) or '<div class="empty">等待20:00晚间信息更新。</div>'}</div><div class="pipeline-card"><h3>08:00 · 隔夜修正</h3>{''.join(f'<div class="news"><b>{esc(x.get("title",""))}</b><small>{esc(x.get("pubDate",""))}</small></div>' for x in (m.get('overnight_headlines') or [])[:8]) or '<div class="empty">等待08:00隔夜信息更新。</div>'}</div></div></section>
<section><h2>④ 完整候选池</h2><p class="muted">完整候选池自动读取，不折叠、不需要点击。</p><div class="toolbar"><input id="q" oninput="filterRows()" placeholder="搜索股票 / 代码 / 板块"><select id="pool" onchange="filterRows()"><option>全部</option><option>重点观察</option><option>预备池</option><option>观察池</option><option>淘汰</option></select><select id="sort" onchange="filterRows()"><option value="score">调整分</option><option value="change">涨幅</option><option value="tier">优先级</option></select></div><div id="rows" class="table-wrap"><div class="empty">正在加载完整候选池…</div></div></section>
<div class="footer">七因子决策系统 · 仅供研究参考，不构成投资建议</div></div><script>
const DATA_URL='{BASE}data/seven_factor_latest.json'; let all=[];
function render(){const q=(document.getElementById('q').value||'').toLowerCase(),p=document.getElementById('pool').value,s=document.getElementById('sort').value;let a=all.filter(r=>(p==='全部'||r.pool===p)&&(!q||(`${{r.name||''}} ${{r.code||''}} ${{r.sector||''}} ${{r.sw_industry||''}}`).toLowerCase().includes(q)));a.sort((x,y)=>s==='change'?Number(y.change_pct||0)-Number(x.change_pct||0):s==='tier'?Number(x.recency?.tier||99)-Number(y.recency?.tier||99):Number(y.adjusted_total||0)-Number(x.adjusted_total||0));let h='<table class="table"><thead><tr><th>#</th><th>股票</th><th>池</th><th>P</th><th>调整分</th><th>涨幅</th><th>三共振</th></tr></thead><tbody>';a.forEach((r,i)=>{{h+=`<tr><td>${{i+1}}</td><td><b>${{r.name||'-'}}</b><br><small>${{r.code||'-'}} · ${{r.sector||'-'}}</small></td><td>${{r.pool||'-'}}</td><td>P${{r.recency?.tier??'-'}}</td><td>${{Number(r.adjusted_total||0).toFixed(1)}}</td><td>${{Number(r.change_pct||0).toFixed(1)}}%</td><td>${{r.resonance?.count??0}}/3</td></tr>`}});h+='</tbody></table>';document.getElementById('rows').innerHTML=h}}
function filterRows(){{render()}}
fetch(DATA_URL).then(r=>r.json()).then(d=>{{all=d.candidates||[];render()}}).catch(()=>document.getElementById('rows').innerHTML='<div class="empty">完整候选池加载失败。</div>');
</script></body></html>'''
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:f.write(html_page)
    print(f'generated live dashboard: {OUT}, candidates={len(d["candidates"])}')
if __name__=='__main__':main()
