#!/usr/bin/env python3
"""Stable dashboard generator with full candidate pool embedded in HTML."""
import html, json, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,'data'); OUT=os.path.join(ROOT,'docs','index.html')

def esc(v): return html.escape(str(v if v is not None else '-'))
def num(v,d=0.0):
    try:return float(v)
    except:return d
def pct(v):return f'{num(v):+.1f}%'
def cls(v):return 'up' if num(v)>=0 else 'down'
def load(name):
    p=os.path.join(DATA,name)
    try:
        with open(p,encoding='utf-8') as f:return json.load(f)
    except Exception:return {}

def action(s):
    x=num(s.get('sentiment_score'),50)
    if x<40:return '谨慎观察','市场偏弱，等待确认，不因为个股高分强行出手'
    if x<55:return '轻仓试错','市场偏弱，优先等待主线与资金确认'
    if x<70:return '结构性参与','围绕强板块挑核心，重点观察池优先'
    return '积极参与','市场进攻条件较好，优先主线核心与首板前候选'

def focus_card(r,i):
    rec=r.get('recency') or {}; res=r.get('resonance') or {}; hist=r.get('history') or {}; rc=int(num(res.get('count'),0)); dots='●'*rc+'○'*max(0,3-rc); w=r.get('next_day_watch') or ['等待信号确认']
    return f'<article class="focus"><div class="rank">TOP {i}</div><div class="fmain"><div><b>{esc(r.get("name"))}</b><small>{esc(r.get("code"))} · {esc(r.get("sector","未分类"))}</small></div><strong>{num(r.get("adjusted_total")):.1f}</strong><span class="pill">P{esc(rec.get("tier","-"))}</span></div><div class="metrics"><span>三共振 <b class="gold">{dots}</b></span><span>连板概率 <b>{esc(r.get("lianban_probability"))}%</b></span><span>涨幅 <b class="{cls(r.get("change_pct"))}">{pct(r.get("change_pct"))}</b></span><span>换手 <b>{esc(r.get("turnover_rate"))}%</b></span><span>历史涨停 <b>{esc(hist.get("limit_up_count"))}</b></span><span>距上次 <b>{esc(hist.get("days_since_last_lu"))}日</b></span></div><div class="watch"><b>次日重点</b><span>{esc(w[0])}</span><span>{esc(w[1]) if len(w)>1 else '-'}</span></div></article>'

def full_rows(candidates):
    rows=[]
    for i,r in enumerate(candidates,1):
        rec=r.get('recency') or {}; res=r.get('resonance') or {}
        rows.append(f'<tr><td>{i}</td><td><b>{esc(r.get("name"))}</b><br><small>{esc(r.get("code"))} · {esc(r.get("sector","-"))}</small></td><td>{esc(r.get("pool","-"))}</td><td>P{esc(rec.get("tier","-"))}</td><td>{num(r.get("adjusted_total")):.1f}</td><td class="{cls(r.get("change_pct"))}">{pct(r.get("change_pct"))}</td><td>{esc(res.get("count",0))}/3</td></tr>')
    return ''.join(rows)

def render(d,e,m):
    sent=d.get('market_sentiment') or {}; c=list(d.get('candidates') or []); act,desc=action(sent)
    ordered=sorted(c,key=lambda r:(int(num((r.get('recency') or {}).get('tier'),99)),-num(r.get('adjusted_total')))); focus=[r for r in ordered if r.get('pool')=='重点观察'][:8]
    ready=sum(r.get('pool')=='预备池' for r in c); watch=sum(r.get('pool')=='观察池' for r in c)
    sectors=sorted(d.get('sector_rankings') or [],key=lambda x:num(x.get('avg_change')),reverse=True)[:6]
    concepts=sorted(d.get('concept_rankings') or [],key=lambda x:num(x.get('avg_change')),reverse=True)[:10]
    sec=''.join(f'<div class="sector"><b>{esc(x.get("name"))}</b><strong class="{cls(x.get("avg_change"))}">{pct(x.get("avg_change"))}</strong><small>{esc(x.get("limit_up_count"))}涨停 · {esc(x.get("strong_count"))}强势</small></div>' for x in sectors)
    con=''.join(f'<span class="concept">#{esc(x.get("rank"))} {esc(x.get("name"))} <em class="{cls(x.get("avg_change"))}">{pct(x.get("avg_change"))}</em></span>' for x in concepts)
    ef=''.join(f'<span class="pill">{esc(x.get("name"))} {esc(x.get("score"))}</span>' for x in (e.get('focus_candidates') or [])[:8])
    en=''.join(f'<div class="news"><b>{esc(x.get("title",""))}</b><small>{esc(x.get("pubDate",""))}</small></div>' for x in (e.get('headlines') or [])[:8]) or '<div class="empty">等待20:00晚间信息更新。</div>'
    mn=''.join(f'<div class="news"><b>{esc(x.get("title",""))}</b><small>{esc(x.get("pubDate",""))}</small></div>' for x in (m.get('overnight_headlines') or [])[:8]) or '<div class="empty">等待08:00隔夜信息更新。</div>'
    rows=full_rows(c)
    css='''<style>:root{--bg:#0a0d12;--p:#121720;--p2:#171e28;--l:#283241;--t:#e8eef7;--m:#8792a4;--up:#ff6575;--down:#35d09a;--gold:#f5c85b}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}.wrap{max-width:1480px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:20px}.title{font-size:27px;font-weight:900}.muted,small,.meta{color:var(--m)}.meta{text-align:right;font-size:11px;line-height:1.8}.hero,.layout,.pipeline{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-top:14px}.box,.section{background:var(--p);border:1px solid var(--l);border-radius:15px}.box{padding:18px}.action{font-size:29px;font-weight:900}.metrics,.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.stats{grid-template-columns:1fr 1fr;padding:18px}.metric,.stat{padding:10px;background:#10151d;border:1px solid #222c38;border-radius:9px}.metric span,.stat span{display:block;color:var(--m);font-size:10px}.metric b,.stat b{display:block;margin-top:4px;font-size:17px}.stat b{font-size:25px}.up{color:var(--up)}.down{color:var(--down)}.gold{color:var(--gold)}.section{padding:16px;margin-top:14px}.focus-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.focus{background:var(--p2);border:1px solid var(--l);border-radius:12px;padding:13px}.rank{font-size:10px;color:var(--gold)}.fmain{display:grid;grid-template-columns:1fr 80px 45px;gap:8px;align-items:center;margin-top:5px}.fmain b{font-size:15px}.fmain small{display:block;font-size:9px;margin-top:3px}.fmain>strong{font-size:21px;text-align:right}.pill{display:inline-flex;padding:4px 7px;border-radius:6px;background:#202932;color:#c8d3e2;font-size:9px}.metrics{grid-template-columns:repeat(6,1fr);margin:11px 0}.metrics span{background:#10151d;border:1px solid #212b37;border-radius:7px;padding:7px;color:var(--m);font-size:9px}.metrics b{display:block;color:var(--t);margin-top:3px}.watch{display:flex;gap:8px;background:#0f141b;border-radius:7px;padding:8px;font-size:10px}.watch span{color:var(--m)}.layout{grid-template-columns:1.05fr .95fr}.sector{display:grid;grid-template-columns:1fr 70px 120px;gap:8px;padding:9px 10px;background:#10151d;border:1px solid #212b37;border-radius:8px;margin-bottom:7px}.concepts{display:flex;flex-wrap:wrap;gap:7px}.concept{padding:8px 9px;background:#10151d;border:1px solid #212b37;border-radius:8px;font-size:10px}.concept em{font-style:normal;margin-left:6px}.pipeline{grid-template-columns:1fr 1fr}.pipeline-card{padding:14px;background:#10151d;border:1px solid #222c38;border-radius:10px}.pipeline-card h3{margin:0 0 8px;font-size:13px}.news{padding:8px 0;border-bottom:1px solid #222b36}.news b{display:block;font-size:10px}.news small{font-size:9px}.empty{padding:18px;text-align:center;color:var(--m);background:#0f141b;border-radius:8px}.pool-tools{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.pool-tools input,.pool-tools select{background:#0f141b;border:1px solid #273140;color:var(--t);padding:8px;border-radius:8px}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:8px;border-bottom:1px solid #222b36;text-align:left;font-size:10px}.table th{color:var(--m)}.table-wrap{max-height:700px;overflow:auto}.footer{text-align:center;color:#5d6979;font-size:10px;padding:18px}@media(max-width:1000px){.hero,.layout,.pipeline{grid-template-columns:1fr}.focus-grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:620px){.wrap{padding:12px}.top{align-items:flex-start;flex-direction:column}.meta{text-align:left}.metrics,.stats{grid-template-columns:repeat(2,1fr)}.metrics{grid-template-columns:1fr 1fr}.sector{grid-template-columns:1fr 60px}.sector small{display:none}}</style>'''
    js='''<script>const tableBody=document.getElementById('poolBody');function filterPool(){const q=(document.getElementById('q').value||'').toLowerCase(),p=document.getElementById('pool').value;for(const tr of tableBody.rows){const t=tr.innerText.toLowerCase();tr.style.display=(p==='全部'||t.includes(p))&&(!q||t.includes(q))?'':'none'}}</script>'''
    html='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七因子 · 决策仪表盘</title>'''+css+f'''</head><body><div class="wrap"><div class="top"><div><div class="title">七因子 · 决策仪表盘</div><div class="muted">收盘选股 → 晚间预判 → 隔夜修正 → 竞价确认</div></div><div class="meta">扫描 {esc(d.get('scan_date'))} {esc(d.get('scan_time'))}<br>20:00：{'已生成' if e else '尚未生成'}<br>08:00：{'已生成' if m else '尚未生成'}</div></div><section class="hero"><div class="box"><div class="muted">当前市场状态</div><div class="action">{esc(act)}</div><div class="muted">情绪分 {num(sent.get('sentiment_score')):.1f} · {esc(sent.get('sentiment_label','正常'))}</div><p class="muted">{esc(desc)}</p><div class="metrics"><div class="metric"><span>涨停</span><b class="up">{esc(sent.get('limit_up_count'))}</b></div><div class="metric"><span>跌停</span><b class="down">{esc(sent.get('limit_down_count'))}</b></div><div class="metric"><span>最高连板</span><b>{esc(sent.get('max_boards_est'))}</b></div><div class="metric"><span>炸板率</span><b>{esc(sent.get('explosion_rate'))}%</b></div></div></div><div class="box stats"><div class="stat"><span>重点观察</span><b>{len(focus)}</b></div><div class="stat"><span>预备池</span><b>{ready}</b></div><div class="stat"><span>观察池</span><b>{watch}</b></div><div class="stat"><span>完整候选池</span><b>{len(c)}</b></div></div></section><section class="section"><h2>① 明日重点观察</h2><p class="muted">先看重点池，再看完整候选池</p><div class="focus-grid">{''.join(focus_card(r,i+1) for i,r in enumerate(focus))}</div></section><section class="section"><h2>② 主线与板块</h2><div class="layout"><div>{sec or '<div class="empty">暂无行业数据</div>'}</div><div class="concepts">{con or '<div class="empty">暂无概念数据</div>'}</div></div></section><section class="section"><h2>③ 晚间预判 / 隔夜修正</h2><div class="pipeline"><div class="pipeline-card"><h3>20:00 · 明日预判</h3><div>{ef or '<span class="pill">20:00 尚未运行</span>'}</div>{en}</div><div class="pipeline-card"><h3>08:00 · 隔夜修正</h3><div><span class="pill">{'已生成' if m else '等待08:00'}</span></div>{mn}</div></div></section><section class="section"><h2>④ 完整候选池 <span class="muted">{len(c)}只 · 页面内完整保留</span></h2><div class="pool-tools"><input id="q" oninput="filterPool()" placeholder="搜索股票 / 代码 / 板块"><select id="pool" onchange="filterPool()"><option>全部</option><option>重点观察</option><option>预备池</option><option>观察池</option><option>淘汰</option></select></div><div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>股票</th><th>池</th><th>P</th><th>调整分</th><th>涨幅</th><th>三共振</th></tr></thead><tbody id="poolBody">{rows}</tbody></table></div></section><div class="footer">七因子决策系统 · 仅供研究参考，不构成投资建议</div></div>{js}</body></html>'''
    return html

def main():
    d=load('seven_factor_latest.json')
    if not d.get('candidates'):raise RuntimeError('candidate pool empty; refuse to overwrite dashboard')
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:f.write(render(d,load('evening_latest.json'),load('morning_latest.json')))
    print(f'generated full dashboard: {len(d["candidates"])} candidates')
if __name__=='__main__':main()
