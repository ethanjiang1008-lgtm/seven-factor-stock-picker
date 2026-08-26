#!/usr/bin/env python3
"""Generate the GitHub Pages decision dashboard.

UI-only layer: reads seven_factor_latest.json and writes docs/index.html.
Scanner, scoring, data fetching and workflow logic are intentionally untouched.
"""
import html
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
LATEST_JSON = os.path.join(DATA_DIR, "seven_factor_latest.json")
OUTPUT_HTML = os.path.join(DOCS_DIR, "index.html")


def load_data():
    with open(LATEST_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def esc(value):
    return html.escape(str(value if value is not None else "-"), quote=True)


def pct(value):
    try:
        return f"{float(value):+.1f}%"
    except Exception:
        return esc(value)


def pct_cls(value):
    try:
        return "up" if float(value) >= 0 else "down"
    except Exception:
        return "muted"


def normalize_list(value, limit=8):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            if isinstance(v, (list, tuple, set)):
                out.extend(f"{k}: {x}" for x in list(v)[:limit])
            else:
                out.append(f"{k}: {v}")
        return [str(x) for x in out[:limit]]
    try:
        return [str(x) for x in list(value)[:limit]]
    except TypeError:
        return [str(value)]


def safe_num(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


def slim_stock(stock):
    scores = stock.get("scores", {}) or {}
    details = stock.get("score_details", {}) or {}
    hist = stock.get("history", {}) or {}
    rec = stock.get("recency", {}) or {}
    resonance = stock.get("resonance", {}) or {}
    return {
        "code": stock.get("code", ""), "name": stock.get("name", ""),
        "sector": stock.get("sector", ""), "sw_industry": stock.get("sw_industry", ""),
        "price": stock.get("price", "-"), "change_pct": stock.get("change_pct", 0),
        "turnover_rate": stock.get("turnover_rate", "-"), "circ_mcap_yi": stock.get("circ_mcap_yi", "-"),
        "adjusted_total": stock.get("adjusted_total", 0), "pool": stock.get("pool", "-"),
        "grade": stock.get("grade", "-"), "scores_total": scores.get("total", "-"),
        "tier": rec.get("tier", 99), "tier_label": rec.get("tier_label", "-"), "tag": rec.get("tag", "-"),
        "resonance": resonance.get("count", 0), "lianban_probability": stock.get("lianban_probability", "-"),
        "limit_up_count": hist.get("limit_up_count", "-"), "max_consecutive": hist.get("max_consecutive", "-"),
        "days_since_last_lu": hist.get("days_since_last_lu", "-"),
        "next_day_watch": normalize_list(stock.get("next_day_watch")),
        "capital_signals": normalize_list(stock.get("capital_signals")),
        "kline_signals": normalize_list(stock.get("kline_signals")),
        "concepts": normalize_list(stock.get("all_concepts"), 5),
        "scoring_source": "概念板块" if stock.get("scoring_source") == "concept" else "申万行业",
        "recent_adjustment": details.get("近期涨停调整", 0),
        "factor_scores": {
            "个股辨识度": scores.get("stock_recognition", 0), "资金预热": scores.get("capital_preheat", 0),
            "K线筹码": scores.get("kline_chip", 0), "题材催化": scores.get("theme_catalyst", 0),
            "板块强度": scores.get("sector_strength", 0), "市值流动性": scores.get("market_cap_liquidity", 0),
            "情绪环境": scores.get("sentiment", 0),
        },
        "factor_details": {
            "个股辨识度": details.get("个股辨识度", ""), "资金预热": details.get("资金预热", ""),
            "K线筹码": details.get("K线筹码", ""), "题材催化": details.get("题材催化", ""),
            "板块强度": details.get("板块强度", ""), "市值流动性": details.get("市值流动性", ""),
            "情绪环境": details.get("情绪环境", ""),
        },
    }


def generate_html(data):
    sent = data.get("market_sentiment", {}) or {}
    summary = data.get("summary", {}) or {}
    candidates = [slim_stock(x) for x in (data.get("candidates", []) or [])]
    candidates.sort(key=lambda x: ({"重点观察":0,"预备池":1,"观察池":2,"淘汰":3}.get(x.get("pool"),9), safe_num(x.get("tier",99),99), -safe_num(x.get("adjusted_total",0))))
    score = safe_num(sent.get("sentiment_score",50),50)
    state, action = ("强势","进攻优先") if score>=70 else (("偏强","精选参与") if score>=55 else (("震荡","控制仓位") if score>=40 else ("偏弱","防守观察")))
    focus=[x for x in candidates if x.get("pool")=="重点观察"][:3]
    focus_text=" · ".join(f"{x.get('name','-')} {x.get('adjusted_total','-')}" for x in focus) or "暂无"
    risk="炸板率偏高，强势股分化需要验证" if safe_num(sent.get("explosion_rate",0))>=20 else "高位股仍需关注次日承接"
    validate="观察核心候选是否继续放量、保持趋势并形成题材共振"
    pool_html="".join(f"<span class='chip'><b>{esc(k)}</b>{esc(v)}只</span>" for k,v in (summary.get("pool_distribution",{}) or {}).items())
    weight_html="".join(f"<span class='chip'><b>{esc(k)}</b>{esc(v)}分</span>" for k,v in data.get("weight_config",{}).items())
    threshold_html="".join(f"<span class='chip'><b>{esc(k)}</b>{esc(v)}</span>" for k,v in data.get("threshold",{}).items())
    sector_rows="".join(f"<tr><td>{esc(s.get('rank'))}</td><td>{esc(s.get('name'))}</td><td class='{pct_cls(s.get('avg_change'))}'>{pct(s.get('avg_change'))}</td><td>{esc(s.get('limit_up_count'))}</td><td>{esc(s.get('strong_count'))}</td></tr>" for s in data.get("sector_rankings",[])[:10])
    concept_tags="".join(f"<span class='concept-tag'><b>{esc(c.get('rank'))}</b>{esc(c.get('name'))}<em>{pct(c.get('avg_change'))}</em></span>" for c in data.get("concept_rankings",[])[:12])
    payload={"scan_date":data.get("scan_date",""),"scan_time":data.get("scan_time",""),"system_version":data.get("system_version",""),"model":data.get("model",""),"market":{"limit_up_count":sent.get("limit_up_count","-"),"limit_down_count":sent.get("limit_down_count","-"),"strong_count":sent.get("strong_count","-"),"explosion_rate":sent.get("explosion_rate","-"),"max_boards_est":sent.get("max_boards_est","-"),"sentiment_score":sent.get("sentiment_score","-"),"sentiment_label":sent.get("sentiment_label","-")},"candidates":candidates}
    payload_json=json.dumps(payload,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
    # Compact UI template: same functionality, only 50 visible cards at once.
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七因子股票决策仪表盘</title><style>body{{margin:0;background:#0b0f14;color:#edf2f7;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}.container{{max-width:1500px;margin:auto;padding:20px}}.section{{background:#121821;border:1px solid #263241;border-radius:14px;padding:16px;margin-bottom:14px}}.decision,.market,.layout2{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.decision{{grid-template-columns:repeat(5,1fr)}}.decision-item,.metric,.chip,.concept-tag{{background:#171f2a;border:1px solid #263241;border-radius:9px;padding:10px}}.decision-item label,.metric span,.meta,.muted{{display:block;color:#7e8a9b;font-size:11px}}.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}.table{{width:100%;border-collapse:collapse}}.table th,.table td{{padding:8px;border-bottom:1px solid #263241;font-size:12px;text-align:left}}.concepts,.chips,.filters{{display:flex;flex-wrap:wrap;gap:7px}.filters{{margin-bottom:12px}}input,select,button{{background:#10161f;color:#edf2f7;border:1px solid #263241;border-radius:8px;padding:8px 10px}}input{{min-width:240px}}.stock-list{{display:flex;flex-direction:column;gap:10px}}.stock-card{{background:#121821;border:1px solid #263241;border-radius:13px;overflow:hidden;content-visibility:auto;contain-intrinsic-size:230px}}.stock-main{{display:grid;grid-template-columns:35px 1.4fr 110px 150px 220px 65px;gap:10px;align-items:center;padding:12px 14px}}.stock-name{{font-size:16px;font-weight:800}}.stock-meta,.score small,.quick-grid span,.quick-grid em,.watch-row,.factor-detail{{color:#7e8a9b;font-size:11px}}.stock-meta{{margin-top:4px}}.score b{{font-size:21px}}.score-bar,.factor-bar{{height:5px;background:#2b3340;border-radius:8px;overflow:hidden;margin:4px 0}}.score-bar i,.factor-bar i{{display:block;height:100%;background:#5b9cff}}.badges{{display:flex;gap:5px;flex-wrap:wrap}}.pill,.tag{{background:#16283f;padding:4px 7px;border-radius:6px;font-size:10px}}.quick-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;padding:0 14px 12px}}.quick-grid>div{{background:#10161f;border:1px solid #202a36;border-radius:9px;padding:8px}}.quick-grid b{{display:block;font-size:14px}}.stock-detail{{display:none;border-top:1px solid #263241;padding:14px}}.stock-card.open .stock-detail{{display:block}}.detail-columns{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.pagination{{display:flex;justify-content:center;gap:6px;margin-top:14px}}@media(max-width:1000px){{.decision,.market,.layout2{{grid-template-columns:1fr 1fr}}.metrics{{grid-template-columns:repeat(3,1fr)}}.stock-main{{grid-template-columns:30px 1fr 90px}}.score,.badges{{display:none}}.quick-grid{{grid-template-columns:repeat(3,1fr)}}}@media(max-width:620px){{.decision{{grid-template-columns:1fr 1fr}}.metrics,.quick-grid{{grid-template-columns:repeat(2,1fr)}}.stock-main{{grid-template-columns:24px 1fr 70px}}.detail-columns{{grid-template-columns:1fr}}input{{width:100%;min-width:0}}}}</style></head><body><div class="container"><header style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:16px"><div><h1 style="margin:0">七因子股票决策仪表盘</h1><div class="muted">{esc(data.get("model",""))}</div></div><div class="meta">{esc(data.get("scan_date",""))} · {esc(data.get("scan_time",""))}</div></header><section class="section"><b>今日决策卡</b><div class="decision" style="margin-top:10px"><div class="decision-item"><label>市场状态</label><b>{esc(state)}</b></div><div class="decision-item"><label>操作倾向</label><b>{esc(action)}</b></div><div class="decision-item"><label>核心关注</label><b>{esc(focus_text)}</b></div><div class="decision-item"><label>主要风险</label><b>{esc(risk)}</b></div><div class="decision-item"><label>明日验证</label><b>{esc(validate)}</b></div></div></section><section class="market"><div class="section"><b>市场情绪</b><div style="font-size:40px;font-weight:900">{esc(sent.get("sentiment_score","-"))}</div><div class="muted">{esc(sent.get("sentiment_label",state))}</div></div><div class="section"><b>关键指标</b><div class="metrics" style="margin-top:10px"><div class="metric"><span>涨停</span><b>{esc(sent.get("limit_up_count","-"))}</b></div><div class="metric"><span>跌停</span><b>{esc(sent.get("limit_down_count","-"))}</b></div><div class="metric"><span>强势</span><b>{esc(sent.get("strong_count","-"))}</b></div><div class="metric"><span>炸板率</span><b>{esc(sent.get("explosion_rate","-"))}%</b></div><div class="metric"><span>最高连板</span><b>{esc(sent.get("max_boards_est","-"))}</b></div><div class="metric"><span>候选</span><b>{len(candidates)}</b></div></div></div></section><section class="layout2"><div class="section"><b>板块强度 TOP10</b><table class="table"><thead><tr><th>#</th><th>板块</th><th>均涨</th><th>涨停</th><th>强势</th></tr></thead><tbody>{sector_rows}</tbody></table></div><div class="section"><b>热门概念 TOP12</b><div class="concepts" style="margin-top:10px">{concept_tags}</div><div class="chips" style="margin-top:10px">{pool_html}</div><div class="chips" style="margin-top:7px">{weight_html}</div><div class="chips" style="margin-top:7px">{threshold_html}</div></div></section><section class="section" id="candidateSection"><b>候选池</b><div class="filters" style="margin-top:10px"><input id="search" placeholder="搜索股票 / 代码 / 板块"><select id="pool"><option>全部</option><option>重点观察</option><option>预备池</option><option>观察池</option><option>淘汰</option></select><select id="grade"><option>全部评级</option><option>A</option><option>B</option><option>C</option><option>D</option></select><select id="sort"><option value="default">推荐排序</option><option value="score">调整分高→低</option><option value="change">涨幅高→低</option><option value="prob">连板概率高→低</option></select><span id="count" class="meta"></span></div><div id="stockList" class="stock-list"></div><div id="pagination" class="pagination"></div></section></div><script id="app-data" type="application/json">{payload_json}</script><script>const DATA=JSON.parse(document.getElementById('app-data').textContent),PAGE_SIZE=50;let state={{page:1,pool:'全部',grade:'全部评级',sort:'default',q:'',openCode:''}};const $=id=>document.getElementById(id);function E(v){{const d=document.createElement('div');d.textContent=v==null?'-':String(v);return d.innerHTML}}function filtered(){{const q=state.q.trim().toLowerCase();let a=DATA.candidates.filter(s=>{{const h=(s.name+' '+s.code+' '+(s.sector||'')+' '+(s.sw_industry||'')).toLowerCase();return(state.pool==='全部'||s.pool===state.pool)&&(state.grade==='全部评级'||s.grade===state.grade)&&(!q||h.includes(q))}});a.sort((x,y)=>state.sort==='score'?Number(y.adjusted_total||0)-Number(x.adjusted_total||0):state.sort==='change'?Number(y.change_pct||0)-Number(x.change_pct||0):state.sort==='prob'?Number(y.lianban_probability||0)-Number(x.lianban_probability||0):(Number(x.tier||99)-Number(y.tier||99))||(Number(y.adjusted_total||0)-Number(x.adjusted_total||0));return a}}function card(s,i){{const open=s.code===state.openCode;return '<article class="stock-card '+(open?'open':'')+'"><div class="stock-main"><div>'+i+'</div><div><div class="stock-name">'+E(s.name)+' <span>'+E(s.code)+'</span></div><div class="stock-meta">'+E(s.sector||'未分类')+' · '+E(s.sw_industry||'未分类')+' · P'+E(s.tier)+'</div></div><div><b>'+E(s.price)+'</b><div>'+E(s.change_pct)+'%</div></div><div class="score"><b>'+E(s.adjusted_total)+'</b><div class="score-bar"><i style="width:'+Math.min(100,Number(s.adjusted_total)||0)+'%"></i></div><small>原始 '+E(s.scores_total)+'</small></div><div class="badges"><span class="pill">'+E(s.pool)+'</span> <span class="pill">'+E(s.grade)+'</span> <span class="pill">'+E(s.tag)+'</span></div><button onclick="toggleDetail(\''+E(s.code)+'\')">'+(open?'收起':'展开')+'</button></div><div class="quick-grid"><div><span>三共振</span><b>'+E(s.resonance)+' / 3</b></div><div><span>连板概率</span><b>'+E(s.lianban_probability)+'%</b></div><div><span>涨停历史</span><b>'+E(s.limit_up_count)+'次</b></div><div><span>最高连板</span><b>'+E(s.max_consecutive)+'连</b></div><div><span>换手率</span><b>'+E(s.turnover_rate)+'%</b></div><div><span>流通市值</span><b>'+E(s.circ_mcap_yi)+'亿</b></div></div><div class="watch-row">明日观察：'+(s.next_day_watch||[]).join(' · ')+'</div>'+(open?'<div class="stock-detail"><div class="detail-columns"><div><b>七因子拆解</b>'+Object.entries(s.factor_scores||{{}}).map(([k,v])=>'<div style="margin:8px 0">'+E(k)+'：'+E(v)+'</div>').join('')+'</div><div><b>证据摘要</b><div>优先级：'+E(s.tier_label)+'</div><div>评分来源：'+E(s.scoring_source)+'</div><div>核心概念：'+E((s.concepts||[]).join(' · '))+'</div><div>资金信号：'+E((s.capital_signals||[]).join(' · '))+'</div><div>K线信号：'+E((s.kline_signals||[]).join(' · '))+'</div></div></div></div>':'')+'</article>'}}function renderPages(t){{const n=Math.max(1,Math.ceil(t/PAGE_SIZE));state.page=Math.min(state.page,n);let h='';for(let p=1;p<=n;p++)if(p===1||p===n||Math.abs(p-state.page)<=2)h+='<button class="page-btn '+(p===state.page?'active':'')+'" onclick="goPage('+p+')">'+p+'</button>';return $('pagination').innerHTML=h}}function render(){{const a=filtered(),start=(state.page-1)*PAGE_SIZE,v=a.slice(start,start+PAGE_SIZE);$('count').textContent='显示 '+(a.length?start+1:0)+'–'+Math.min(start+v.length,a.length)+' / '+a.length+' 只';$('stockList').innerHTML=v.map((s,i)=>card(s,start+i+1)).join('');renderPages(a.length)}}function goPage(p){{state.page=p;state.openCode='';render()}}function toggleDetail(c){{state.openCode=state.openCode===c?'':c;render()}}$('search').addEventListener('input',e=>{{state.q=e.target.value;state.page=1;render()}});$('pool').addEventListener('change',e=>{{state.pool=e.target.value;state.page=1;render()}});$('grade').addEventListener('change',e=>{{state.grade=e.target.value;state.page=1;render()}});$('sort').addEventListener('change',e=>{{state.sort=e.target.value;state.page=1;render()}});render();</script></body></html>'''


def write_page(content):
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(content)


def run():
    data = load_data()
    content = generate_html(data)
    write_page(content)
    print(f"[Pages] 网页已生成：{OUTPUT_HTML}（{len(content)} 字节）")
    return {"output": OUTPUT_HTML, "size": len(content)}


if __name__ == "__main__":
    run()
