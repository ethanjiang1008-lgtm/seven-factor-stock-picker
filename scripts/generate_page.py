#!/usr/bin/env python3
"""Generate the GitHub Pages decision dashboard from seven_factor_latest.json."""
import html
import json
import os
from string import Template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
LATEST_JSON = os.path.join(DATA_DIR, "seven_factor_latest.json")
OUTPUT_HTML = os.path.join(DOCS_DIR, "index.html")


def load_data():
    with open(LATEST_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


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
        return "muted"


def pool_cls(v):
    return {"重点观察":"focus", "预备池":"ready", "观察池":"watch", "淘汰":"drop"}.get(v, "drop")


def grade_cls(v):
    return {"A":"a", "B":"b", "C":"c", "D":"d"}.get(v, "d")


def mood(sent):
    try:
        s = float(sent.get("sentiment_score", 50))
    except Exception:
        s = 50
    return ("hot" if s >= 70 else "warm" if s >= 55 else "cold" if s < 40 else "neutral")


def tags(items, cls="default-tag"):
    items = items or []
    if not items:
        return '<span class="tag muted-tag">暂无</span>'
    return "".join(f'<span class="tag {cls}">{esc(x)}</span>' for x in items[:8])


def factors(r):
    scores = r.get("scores", {})
    details = r.get("score_details", {})
    cfg = [("个股辨识度",25,"stock_recognition"),("资金预热",20,"capital_preheat"),("K线筹码",15,"kline_chip"),("题材催化",10,"theme_catalyst"),("板块强度",10,"sector_strength"),("市值流动性",15,"market_cap_liquidity"),("情绪环境",5,"sentiment")]
    out=[]
    for name,maxv,key in cfg:
        try:
            value=float(scores.get(key,0)); width=max(0,min(100,value/maxv*100))
            val=f"{value:.1f}"
        except Exception:
            width=0; val="-"
        detail=details.get(name+f"(/{maxv})", details.get(name,""))
        out.append(f'<div class="factor"><div class="factor-head"><span>{esc(name)}</span><b>{val}/{maxv}</b></div><div class="bar"><i style="width:{width:.0f}%"></i></div><div class="factor-detail">{esc(detail)}</div></div>')
    return "".join(out)


def stock_card(r, i):
    pool=r.get("pool","-"); grade=r.get("grade","-"); score=r.get("adjusted_total",0)
    rec=r.get("recency",{}); hist=r.get("history",{}); res=r.get("resonance",{})
    try: score_w=max(0,min(100,float(score)))
    except Exception: score_w=0
    rc=int(res.get("count",0) or 0)
    dots="●"*rc+"○"*max(0,3-rc)
    concepts=r.get("all_concepts",[])
    return f'''<article class="stock-card" data-pool="{esc(pool)}" data-grade="{esc(grade)}" data-tier="{esc(rec.get("tier","99"))}" data-name="{esc(r.get("name",""))} {esc(r.get("code",""))} {esc(r.get("sector",""))}">
      <div class="stock-top">
        <div class="rank">#{i}</div>
        <div><div class="stock-name">{esc(r.get("name"))} <span>{esc(r.get("code"))}</span></div><div class="stock-meta"><span>{esc(r.get("sector","未分类"))}</span><span>{esc(r.get("sw_industry","未分类"))}</span><span>{esc(rec.get("tag","-"))}</span></div></div>
        <div class="price-box"><strong>{esc(r.get("price"))}</strong><span class="{pct_cls(r.get("change_pct"))}">{pct(r.get("change_pct"))}</span></div>
        <div class="score-box"><b>{esc(score)}</b><span>/100</span><div class="score-line"><i style="width:{score_w:.0f}%"></i></div><small>原始 {esc(r.get("scores",{}).get("total","-"))}</small></div>
        <div class="labels"><span class="pill {pool_cls(pool)}">{esc(pool)}</span><span class="pill grade-{grade_cls(grade)}">{esc(grade)}</span><span class="pill tier">P{esc(rec.get("tier","-"))}</span></div>
        <button class="detail-btn" onclick="toggleDetail(this)">展开详情</button>
      </div>
      <div class="quick-grid">
        <div><span>三共振</span><b class="resonance">{dots}</b><em>{rc}/3</em></div>
        <div><span>连板概率</span><b>{esc(r.get("lianban_probability","-"))}%</b></div>
        <div><span>涨停历史</span><b>{esc(hist.get("limit_up_count","-"))}次</b><em>最高{esc(hist.get("max_consecutive","-"))}连</em></div>
        <div><span>距上次涨停</span><b>{esc(hist.get("days_since_last_lu","-"))}日</b></div>
        <div><span>换手率</span><b>{esc(r.get("turnover_rate","-"))}%</b></div>
        <div><span>流通市值</span><b>{esc(r.get("circ_mcap_yi","-"))}亿</b></div>
      </div>
      <div class="signal-row"><div><label>明日关注</label>{tags(r.get("next_day_watch"),"watch-tag")}</div><div><label>资金信号</label>{tags(r.get("capital_signals"),"capital-tag")}</div><div><label>K线信号</label>{tags(r.get("kline_signals"),"k-tag")}</div></div>
      <div class="stock-detail"><div class="detail-columns">
        <section><h4>七因子拆解</h4>{factors(r)}</section>
        <section><h4>为什么值得继续观察</h4><div class="reason-box"><div><b>优先级</b><span>{esc(rec.get("tier_label","-"))} · {esc(rec.get("tag","-"))}</span></div><div><b>评分来源</b><span>{'概念板块' if r.get('scoring_source')=='concept' else '申万行业'}</span></div><div><b>近期调整</b><span>{esc(r.get("score_details",{}).get("近期涨停调整",0))}</span></div><div><b>核心概念</b><span>{esc(', '.join(concepts[:5]) if concepts else r.get('concept') or '无')}</span></div></div><div class="next-plan"><b>次日观察重点</b>{tags(r.get("next_day_watch"),"watch-tag")}</div></section>
      </div></div>
    </article>'''


def generate_html(data):
    sent=data.get("market_sentiment",{}); summary=data.get("summary",{}); candidates=data.get("candidates",[])
    pools=summary.get("pool_distribution",{})
    ranked=sorted(candidates,key=lambda x:({"重点观察":0,"预备池":1,"观察池":2,"淘汰":3}.get(x.get("pool"),9), x.get("recency",{}).get("tier",99), -float(x.get("adjusted_total",0))))
    sectors=data.get("sector_rankings",[])[:8]; concepts=data.get("concept_rankings",[])[:10]
    sector_rows="".join(f'<tr><td>{esc(s.get("rank"))}</td><td>{esc(s.get("name"))}</td><td class="{pct_cls(s.get("avg_change"))}">{pct(s.get("avg_change"))}</td><td>{esc(s.get("limit_up_count"))}</td><td>{esc(s.get("strong_count"))}</td></tr>' for s in sectors)
    concept_tags="".join(f'<span class="concept-tag"><b>{esc(c.get("rank"))}</b>{esc(c.get("name"))}<em>{pct(c.get("avg_change"))}</em></span>' for c in concepts)
    weights="".join(f'<span class="chip"><b>{esc(k)}</b>{esc(v)}分</span>' for k,v in data.get("weight_config",{}).items())
    thresholds="".join(f'<span class="chip"><b>{esc(k)}</b>{esc(v)}</span>' for k,v in data.get("threshold",{}).items())
    cards="".join(stock_card(r,i+1) for i,r in enumerate(ranked))
    html_tpl=Template(r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七因子决策仪表盘</title>
<style>
:root{--bg:#0b0e13;--panel:#141922;--panel2:#1a202b;--line:#293140;--text:#e8edf5;--muted:#8590a3;--accent:#5b9cff;--up:#ff5c6c;--down:#35c98b;--gold:#f6c453;--orange:#ff9e43}*{box-sizing:border-box}body{margin:0;background:#0b0e13;color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px}.container{max-width:1500px;margin:auto;padding:22px}.hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:18px}h1{margin:0;font-size:27px}.sub,.meta,.hint,.muted{color:var(--muted)}.sub{margin-top:7px;font-size:13px}.meta{font-size:12px;text-align:right;line-height:1.8}.panel,.section{background:var(--panel);border:1px solid var(--line);border-radius:14px}.market{display:grid;grid-template-columns:1.2fr 2fr;gap:14px;margin-bottom:14px}.market-main{padding:18px}.market-state{display:flex;align-items:center;gap:14px}.state-dot{width:12px;height:12px;border-radius:50%;background:var(--accent)}.state-dot.hot{background:var(--up)}.state-dot.warm{background:var(--orange)}.state-dot.cold{background:var(--down)}.state-title{font-size:21px;font-weight:800}.state-score{font-size:36px;font-weight:900}.state-desc{color:var(--muted);font-size:12px;margin-top:6px}.metric-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-top:18px}.metric,.action-card,.quick-grid>div,.signal-row>div,.detail-columns section{background:#10161f;border:1px solid #212a36;border-radius:10px;padding:10px}.metric span,.quick-grid span,.signal-row label{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}.metric b{font-size:18px}.up{color:var(--up)}.down{color:var(--down)}.actions{padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:10px}.action-card .big{font-size:24px;font-weight:900}.action-card .hint{font-size:11px;margin-top:3px}.action-focus{border-color:#6d3340}.action-ready{border-color:#6a4a2a}.section{margin-bottom:14px;padding:16px}.section-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:12px}.title{font-size:16px;font-weight:800}.layout2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:8px;border-bottom:1px solid var(--line);font-size:12px;text-align:left}.table th{color:var(--muted)}.concepts{display:flex;flex-wrap:wrap;gap:7px}.concept-tag{padding:7px 9px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;font-size:12px}.concept-tag b{color:var(--gold);margin-right:4px}.concept-tag em{font-style:normal;margin-left:7px}.config-line{display:flex;flex-wrap:wrap;gap:7px}.chip{padding:6px 8px;background:#10161f;border:1px solid var(--line);border-radius:7px;font-size:11px;color:var(--muted)}.chip b{color:#cbd6e6;margin-right:4px}.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.filters input,.filters select,.filter-btn{background:#0f141c;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:8px 10px}.filters input{min-width:220px}.filter-btn{color:var(--muted);cursor:pointer}.filter-btn.active{color:#bcd4ff;border-color:#456da6;background:#142137}.count{margin-left:auto;color:var(--muted);font-size:12px}.stock-list{display:flex;flex-direction:column;gap:10px}.stock-card{background:var(--panel);border:1px solid var(--line);border-radius:13px;overflow:hidden}.stock-top{display:grid;grid-template-columns:42px minmax(230px,1.3fr) 110px 150px 220px 80px;gap:12px;align-items:center;padding:13px 14px}.rank{color:var(--muted);font-weight:700}.stock-name{font-weight:800;font-size:16px}.stock-name span{color:var(--muted);font-size:11px}.stock-meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;font-size:11px;color:var(--muted)}.stock-meta span{padding:2px 6px;background:#0f141c;border-radius:5px}.price-box strong{display:block;font-size:18px}.price-box span{font-weight:700}.score-box b{font-size:21px}.score-box span,.score-box small{color:var(--muted);font-size:11px}.score-line,.bar{height:5px;background:#2b3340;border-radius:8px;overflow:hidden}.score-line i,.bar i{display:block;height:100%;background:#5b9cff}.labels{display:flex;flex-wrap:wrap;gap:5px}.pill{display:inline-flex;padding:5px 8px;border-radius:7px;font-size:11px;border:1px solid transparent}.focus{background:#3b1c23;color:#ff9aa6}.ready{background:#3a2817;color:#ffc17b}.watch{background:#16283f;color:#a9c9ff}.drop{background:#1d232c;color:var(--muted)}.tier{background:#171d27;color:#b8c2d1;border-color:var(--line)}.grade-a{background:#3b1c23;color:#ff9aa6}.grade-b{background:#3a2817;color:#ffc17b}.grade-c{background:#16283f;color:#a9c9ff}.grade-d{background:#1d232c;color:var(--muted)}.detail-btn{border:1px solid var(--line);background:#10161f;color:var(--muted);border-radius:8px;padding:7px;cursor:pointer}.quick-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;padding:0 14px 12px}.quick-grid b{display:inline-block;font-size:14px}.quick-grid em{font-size:10px;color:var(--muted);font-style:normal;margin-left:5px}.resonance{color:var(--gold);letter-spacing:1px}.signal-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px;padding:0 14px 13px}.tag{display:inline-block;background:#1d2430;border:1px solid #2a3443;border-radius:6px;padding:3px 6px;font-size:10px;margin:2px}.watch-tag{color:#d9e5ff;border-color:#314b73}.capital-tag{color:#d2f3e3;border-color:#285444}.k-tag{color:#ffe8b8;border-color:#5b4723}.muted-tag{color:var(--muted)}.stock-detail{display:none;border-top:1px solid var(--line);padding:14px;background:#10151d}.stock-card.open .stock-detail{display:block}.detail-columns{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}.detail-columns h4{margin:0 0 10px}.factor{margin:9px 0}.factor-head{display:flex;justify-content:space-between;font-size:11px}.factor-detail{font-size:10px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.reason-box{display:grid;grid-template-columns:1fr 1fr;gap:8px}.reason-box>div{background:#0f141c;border:1px solid #202a36;border-radius:8px;padding:9px}.reason-box b,.next-plan>b{display:block;font-size:10px;color:var(--muted);margin-bottom:5px}.next-plan{margin-top:9px;background:#0f141c;border:1px solid #202a36;border-radius:8px;padding:9px}.footer{text-align:center;color:#566173;font-size:11px;padding:18px}.hide{display:none}
@media(max-width:1000px){.market,.layout2,.detail-columns{grid-template-columns:1fr}.stock-top{grid-template-columns:34px 1fr 90px}.labels,.detail-btn,.score-box{grid-column:2/-1}.quick-grid{grid-template-columns:repeat(3,1fr)}.signal-row{grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:640px){.container{padding:12px}.hero{align-items:flex-start;flex-direction:column}.meta{text-align:left}.metric-grid{grid-template-columns:repeat(2,1fr)}.stock-top{grid-template-columns:26px 1fr 80px}.price-box{text-align:right}.quick-grid{grid-template-columns:repeat(2,1fr)}.filters input{min-width:160px;width:100%}.count{width:100%;margin-left:0}}
</style></head><body><div class="container">
<header class="hero"><div><h1>七因子股票决策仪表盘</h1><div class="sub">$MODEL</div></div><div class="meta">扫描日期：$DATE<br>扫描时间：$TIME · 数据源：新浪财经 API</div></header>
<section class="market"><div class="panel market-main"><div class="market-state"><span class="state-dot $MOOD"></span><div><div class="state-title">$LABEL</div><div class="state-desc">先看市场环境，再看个股。分数用于排序，不等同于买入指令。</div></div><div style="margin-left:auto;text-align:right"><div class="state-score">$SCORE</div><div class="state-desc">情绪分</div></div></div><div class="metric-grid"><div class="metric"><span>涨停</span><b class="up">$LUP</b></div><div class="metric"><span>跌停</span><b class="down">$LDN</b></div><div class="metric"><span>强势股</span><b>$STRONG</b></div><div class="metric"><span>炸板率</span><b>$EXPLODE%</b></div><div class="metric"><span>最高连板</span><b>$MAXBOARD</b></div><div class="metric"><span>冰点状态</span><b>$ICE</b></div><div class="metric"><span>候选总数</span><b>$TOTAL</b></div></div></div><div class="panel actions"><div class="action-card action-focus"><div class="hint">重点观察</div><div class="big">$FOCUS_COUNT 只</div><div class="hint">≥65分 + 三共振</div></div><div class="action-card action-ready"><div class="hint">预备池</div><div class="big">$READY_COUNT 只</div><div class="hint">等待强度或资金确认</div></div><div class="action-card"><div class="hint">观察池</div><div class="big">$WATCH_COUNT 只</div><div class="hint">只做观察</div></div><div class="action-card"><div class="hint">失败记录</div><div class="big">$FAILED</div><div class="hint">扫描异常，不等同于淘汰</div></div></div></section>
<section class="section"><div class="section-head"><div><div class="title">热点与板块</div><div class="hint">先找市场共识，再看个股质量</div></div></div><div class="layout2"><div><table class="table"><thead><tr><th>#</th><th>行业</th><th>均涨幅</th><th>涨停</th><th>强势</th></tr></thead><tbody>$SECTOR_ROWS</tbody></table></div><div><div class="hint" style="margin-bottom:7px">概念强度 TOP10</div><div class="concepts">$CONCEPTS</div></div></div></section>
<section class="section"><div class="section-head"><div><div class="title">模型配置</div><div class="hint">参数放在这里，避免首屏被模型细节占满</div></div></div><div class="config-line">$WEIGHTS</div><div class="config-line" style="margin-top:7px">$THRESHOLDS</div></section>
<section class="section"><div class="section-head"><div><div class="title">候选池</div><div class="hint">按“池 → 优先级 → 调整分”排序，点击展开看证据链</div></div><div class="count" id="count"></div></div><div class="filters"><input id="search" placeholder="搜索股票 / 代码 / 板块"><select id="sort"><option value="score">调整分从高到低</option><option value="recency">优先级优先</option><option value="change">今日涨幅</option><option value="prob">连板概率</option></select><button class="filter-btn active" data-pool="全部">全部</button><button class="filter-btn" data-pool="重点观察">重点观察</button><button class="filter-btn" data-pool="预备池">预备池</button><button class="filter-btn" data-pool="观察池">观察池</button><select id="grade"><option value="全部">全部评级</option><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select></div></section>
<div class="stock-list" id="stockList">$CARDS</div><div class="footer">七因子选股系统 $VERSION · 每工作日 15:35 自动更新 · 数据仅供研究参考，不构成投资建议</div></div>
<script>
const cards=[...document.querySelectorAll('.stock-card')];let pool='全部';
function toggleDetail(btn){const c=btn.closest('.stock-card');c.classList.toggle('open');btn.textContent=c.classList.contains('open')?'收起详情':'展开详情'}
function num(v){const x=parseFloat(v);return isNaN(x)?-99999:x}
function render(){const q=document.getElementById('search').value.trim().toLowerCase(),g=document.getElementById('grade').value,s=document.getElementById('sort').value;let a=cards.filter(c=>(pool==='全部'||c.dataset.pool===pool)&&(g==='全部'||c.dataset.grade===g)&&(!q||c.dataset.name.toLowerCase().includes(q)));a.sort((x,y)=>{if(s==='recency')return num(x.dataset.tier)-num(y.dataset.tier);if(s==='change')return num(y.querySelector('.price-box span').textContent)-num(x.querySelector('.price-box span').textContent);if(s==='prob')return num(y.querySelector('.quick-grid div:nth-child(2) b').textContent)-num(x.querySelector('.quick-grid div:nth-child(2) b').textContent);return num(y.querySelector('.score-box b').textContent)-num(x.querySelector('.score-box b').textContent)});cards.forEach(c=>c.style.display='none');a.forEach(c=>{c.style.display='block';document.getElementById('stockList').appendChild(c)});document.getElementById('count').textContent=`显示 ${a.length} / ${cards.length} 只`}
document.getElementById('search').addEventListener('input',render);document.getElementById('sort').addEventListener('change',render);document.getElementById('grade').addEventListener('change',render);document.querySelectorAll('.filter-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');pool=b.dataset.pool;render()}));render();
</script></body></html>''')
    return html_tpl.substitute(
        MODEL=esc(data.get("model","")), DATE=esc(data.get("scan_date","")), TIME=esc(data.get("scan_time","")), MOOD=mood(sent), LABEL=esc(sent.get("sentiment_label","-")), SCORE=esc(sent.get("sentiment_score","-")),
        LUP=esc(sent.get("limit_up_count","-")), LDN=esc(sent.get("limit_down_count","-")), STRONG=esc(sent.get("strong_count","-")), EXPLODE=esc(sent.get("explosion_rate","-")), MAXBOARD=esc(sent.get("max_boards_est","-")), ICE="是" if sent.get("is_ice_point") else "否", TOTAL=esc(summary.get("total_scanned",len(candidates))),
        FOCUS_COUNT=esc(pools.get("重点观察",0)), READY_COUNT=esc(pools.get("预备池",0)), WATCH_COUNT=esc(pools.get("观察池",0)), FAILED=esc(summary.get("total_failed",0)), SECTOR_ROWS=sector_rows or '<tr><td colspan="5" class="muted">暂无数据</td></tr>', CONCEPTS=concept_tags or '<span class="muted">暂无概念数据</span>', WEIGHTS=weights, THRESHOLDS=thresholds, CARDS=cards, VERSION=esc(data.get("system_version",""))
    )


def run():
    data=load_data(); page=generate_html(data); os.makedirs(DOCS_DIR,exist_ok=True)
    with open(OUTPUT_HTML,"w",encoding="utf-8") as f: f.write(page)
    print(f"[Pages] 决策仪表盘已生成：{OUTPUT_HTML} ({len(page)} bytes)")
    return {"output":OUTPUT_HTML,"size":len(page)}

if __name__=='__main__': run()
