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
    """Keep only fields needed by the UI so the browser does not parse the full raw record."""
    scores = stock.get("scores", {}) or {}
    details = stock.get("score_details", {}) or {}
    hist = stock.get("history", {}) or {}
    rec = stock.get("recency", {}) or {}
    resonance = stock.get("resonance", {}) or {}
    return {
        "code": stock.get("code", ""),
        "name": stock.get("name", ""),
        "sector": stock.get("sector", ""),
        "sw_industry": stock.get("sw_industry", ""),
        "price": stock.get("price", "-"),
        "change_pct": stock.get("change_pct", 0),
        "turnover_rate": stock.get("turnover_rate", "-"),
        "circ_mcap_yi": stock.get("circ_mcap_yi", "-"),
        "adjusted_total": stock.get("adjusted_total", 0),
        "pool": stock.get("pool", "-"),
        "grade": stock.get("grade", "-"),
        "scores_total": scores.get("total", "-"),
        "tier": rec.get("tier", 99),
        "tier_label": rec.get("tier_label", "-"),
        "tag": rec.get("tag", "-"),
        "resonance": resonance.get("count", 0),
        "lianban_probability": stock.get("lianban_probability", "-"),
        "limit_up_count": hist.get("limit_up_count", "-"),
        "max_consecutive": hist.get("max_consecutive", "-"),
        "days_since_last_lu": hist.get("days_since_last_lu", "-"),
        "next_day_watch": normalize_list(stock.get("next_day_watch")),
        "capital_signals": normalize_list(stock.get("capital_signals")),
        "kline_signals": normalize_list(stock.get("kline_signals")),
        "concepts": normalize_list(stock.get("all_concepts"), 5),
        "scoring_source": "概念板块" if stock.get("scoring_source") == "concept" else "申万行业",
        "recent_adjustment": details.get("近期涨停调整", 0),
        "factor_scores": {
            "个股辨识度": scores.get("stock_recognition", 0),
            "资金预热": scores.get("capital_preheat", 0),
            "K线筹码": scores.get("kline_chip", 0),
            "题材催化": scores.get("theme_catalyst", 0),
            "板块强度": scores.get("sector_strength", 0),
            "市值流动性": scores.get("market_cap_liquidity", 0),
            "情绪环境": scores.get("sentiment", 0),
        },
        "factor_details": {
            "个股辨识度": details.get("个股辨识度", ""),
            "资金预热": details.get("资金预热", ""),
            "K线筹码": details.get("K线筹码", ""),
            "题材催化": details.get("题材催化", ""),
            "板块强度": details.get("板块强度", ""),
            "市值流动性": details.get("市值流动性", ""),
            "情绪环境": details.get("情绪环境", ""),
        },
    }


def generate_html(data):
    sent = data.get("market_sentiment", {}) or {}
    summary = data.get("summary", {}) or {}
    raw_candidates = data.get("candidates", []) or []
    candidates = [slim_stock(x) for x in raw_candidates]

    candidates.sort(
        key=lambda x: (
            {"重点观察": 0, "预备池": 1, "观察池": 2, "淘汰": 3}.get(x.get("pool"), 9),
            safe_num(x.get("tier", 99), 99),
            -safe_num(x.get("adjusted_total", 0)),
        )
    )

    sentiment_score = safe_num(sent.get("sentiment_score", 50), 50)
    if sentiment_score >= 70:
        state, action = "强势", "进攻优先"
    elif sentiment_score >= 55:
        state, action = "偏强", "精选参与"
    elif sentiment_score >= 40:
        state, action = "震荡", "控制仓位"
    else:
        state, action = "偏弱", "防守观察"

    focus = [x for x in candidates if x.get("pool") == "重点观察"][:3]
    focus_text = " · ".join(f"{x.get('name', '-') } {x.get('adjusted_total', '-')}" for x in focus) or "暂无"
    risk = "炸板率偏高，强势股分化需要验证" if safe_num(sent.get("explosion_rate", 0)) >= 20 else "高位股仍需关注次日承接"
    validate = "观察核心候选是否继续放量、保持趋势并形成题材共振"

    pool_dist = summary.get("pool_distribution", {}) or {}
    pool_html = "".join(
        f"<span class='chip'><b>{esc(k)}</b>{esc(v)}只</span>" for k, v in pool_dist.items()
    )
    weight_html = "".join(
        f"<span class='chip'><b>{esc(k)}</b>{esc(v)}分</span>" for k, v in data.get("weight_config", {}).items()
    )
    threshold_html = "".join(
        f"<span class='chip'><b>{esc(k)}</b>{esc(v)}</span>" for k, v in data.get("threshold", {}).items()
    )
    sector_rows = "".join(
        f"<tr><td>{esc(s.get('rank'))}</td><td>{esc(s.get('name'))}</td>"
        f"<td class='{pct_cls(s.get('avg_change'))}'>{pct(s.get('avg_change'))}</td>"
        f"<td>{esc(s.get('limit_up_count'))}</td><td>{esc(s.get('strong_count'))}</td></tr>"
        for s in data.get("sector_rankings", [])[:10]
    )
    concept_tags = "".join(
        f"<span class='concept-tag'><b>{esc(c.get('rank'))}</b>{esc(c.get('name'))}<em>{pct(c.get('avg_change'))}</em></span>"
        for c in data.get("concept_rankings", [])[:12]
    )

    payload = {
        "scan_date": data.get("scan_date", ""),
        "scan_time": data.get("scan_time", ""),
        "system_version": data.get("system_version", ""),
        "model": data.get("model", ""),
        "market": {
            "limit_up_count": sent.get("limit_up_count", "-"),
            "limit_down_count": sent.get("limit_down_count", "-"),
            "strong_count": sent.get("strong_count", "-"),
            "explosion_rate": sent.get("explosion_rate", "-"),
            "max_boards_est": sent.get("max_boards_est", "-"),
            "sentiment_score": sent.get("sentiment_score", "-"),
            "sentiment_label": sent.get("sentiment_label", "-"),
        },
        "candidates": candidates,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>七因子股票决策仪表盘 {esc(data.get("system_version", ""))}</title>
<style>
:root{{--bg:#0b0f14;--panel:#121821;--panel2:#171f2a;--line:#263241;--text:#edf2f7;--muted:#7e8a9b;--blue:#5b9cff;--up:#ff6675;--down:#35c98b;--gold:#f6c453;--orange:#ff9f43}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px}}.container{{max-width:1500px;margin:auto;padding:20px}}.header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:16px}}h1{{margin:0;font-size:28px}}.sub{{margin-top:7px;color:var(--muted);font-size:13px}}.meta{{text-align:right;color:var(--muted);font-size:12px;line-height:1.8}}.section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}}.section-title{{font-size:16px;font-weight:800;margin-bottom:12px}}.decision{{display:grid;grid-template-columns:1.25fr 1fr 1fr 1fr 1.5fr;gap:8px}}.decision-item{{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:13px}}.decision-item label{{display:block;color:var(--muted);font-size:11px;margin-bottom:7px}}.decision-item strong{{font-size:17px}}.market{{display:grid;grid-template-columns:1.15fr 2fr;gap:12px}}.market-main{{padding:16px}}.state{{display:flex;align-items:center;gap:12px}}.dot{{width:12px;height:12px;border-radius:50%;background:var(--blue)}}.state-title{{font-size:21px;font-weight:800}}.state-score{{font-size:38px;font-weight:900}}.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:16px}}.metric{{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:10px}}.metric span{{display:block;color:var(--muted);font-size:11px;margin-bottom:4px}}.metric b{{font-size:18px}}.layout2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.table{{width:100%;border-collapse:collapse}}.table th,.table td{{padding:8px;border-bottom:1px solid var(--line);font-size:12px;text-align:left}}.table th{{color:var(--muted)}}.concepts,.chips{{display:flex;flex-wrap:wrap;gap:7px}}.concept-tag,.chip{{padding:7px 9px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;font-size:12px}}.concept-tag b,.chip b{{color:var(--gold);margin-right:5px}}.concept-tag em{{font-style:normal;margin-left:7px}}.filters{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}}.filters input,.filters select,.filter-btn{{background:#0f141b;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:8px 10px}}.filters input{{min-width:240px}}.filter-btn{{cursor:pointer;color:var(--muted)}}.filter-btn.active{{color:#bcd4ff;border-color:#456da6;background:#142137}}.count{{margin-left:auto;color:var(--muted);font-size:12px}}.stock-list{{display:flex;flex-direction:column;gap:10px;min-height:100px}}.stock-card{{background:var(--panel);border:1px solid var(--line);border-radius:13px;overflow:hidden;content-visibility:auto;contain-intrinsic-size:230px}}.stock-main{{display:grid;grid-template-columns:42px minmax(220px,1.35fr) 110px 150px 220px 70px;gap:12px;align-items:center;padding:13px 14px}}.rank{{color:var(--muted);font-weight:700}}.stock-name{{font-weight:800;font-size:16px}}.stock-name span{{color:var(--muted);font-size:11px}}.stock-meta{{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;color:var(--muted);font-size:11px}}.stock-meta span{{padding:2px 6px;background:#0f141b;border-radius:5px}}.price strong{{display:block;font-size:18px}}.price span{{font-weight:700}}.score b{{font-size:21px}}.score small{{color:var(--muted);font-size:11px}}.score-bar,.factor-bar{{height:5px;background:#2b3340;border-radius:8px;overflow:hidden;margin:4px 0}}.score-bar i,.factor-bar i{{display:block;height:100%;background:var(--blue)}}.score-bar i.hot{{background:var(--up)}}.score-bar i.warm{{background:var(--orange)}}.score-bar i.cool{{background:var(--blue)}}.score-bar i.muted{{background:#66717f}}.badges{{display:flex;flex-wrap:wrap;gap:5px}}.pill{{display:inline-flex;padding:5px 8px;border-radius:7px;font-size:11px}}.focus{{background:#3b1c23;color:#ff9aa6}}.ready{{background:#3a2817;color:#ffc17b}}.watch{{background:#16283f;color:#a9c9ff}}.drop{{background:#1d232c;color:var(--muted)}}.grade-a{{background:#3b1c23;color:#ff9aa6}}.grade-b{{background:#3a2817;color:#ffc17b}}.grade-c{{background:#16283f;color:#a9c9ff}}.grade-d{{background:#1d232c;color:var(--muted)}}.tier{{background:#171d27;color:#b8c2d1;border:1px solid var(--line)}}.detail-btn{{border:1px solid var(--line);background:#10161f;color:var(--muted);border-radius:8px;padding:7px;cursor:pointer}}.quick-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;padding:0 14px 12px}}.quick-grid>div{{background:#10161f;border:1px solid #202a36;border-radius:9px;padding:9px}}.quick-grid span{{display:block;color:var(--muted);font-size:11px;margin-bottom:4px}}.quick-grid b{{font-size:15px}}.quick-grid em{{display:block;color:var(--muted);font-size:10px;font-style:normal;margin-top:2px}}.watch-row{{padding:0 14px 12px;color:var(--muted);font-size:11px}}.watch-row label{{display:block;margin-bottom:5px}}.tag{{display:inline-block;padding:3px 6px;border-radius:5px;background:#1b2430;border:1px solid #293443;color:#bac7d6;margin:2px;font-size:10px}}.muted-tag{{color:#6f7b89}}.stock-detail{{display:none;border-top:1px solid var(--line);padding:14px;background:#0f151d}}.stock-card.open .stock-detail{{display:block}}.detail-columns{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.detail-columns section{{background:#121a23;border:1px solid var(--line);border-radius:10px;padding:12px}}.detail-columns h4{{margin:0 0 10px;font-size:13px}}.factor-row{{margin-bottom:10px}}.factor-head{{display:flex;justify-content:space-between;font-size:11px;color:#c4ceda}}.factor-detail{{margin-top:4px;color:var(--muted);font-size:10px;line-height:1.4}}.evidence div{{display:flex;justify-content:space-between;gap:20px;border-bottom:1px dashed #263241;padding:8px 0;font-size:11px}}.evidence b{{color:#aab6c6}}.evidence span{{color:#dbe3ec;text-align:right}}.pagination{{display:flex;justify-content:center;align-items:center;gap:6px;margin-top:14px;flex-wrap:wrap}}.page-btn{{min-width:34px;padding:7px 9px;background:#10161f;border:1px solid var(--line);color:var(--muted);border-radius:8px;cursor:pointer}}.page-btn.active{{background:#142137;border-color:#456da6;color:#cfe0ff}}.page-info{{color:var(--muted);font-size:12px;margin:0 8px}}.footer{{text-align:center;color:#596575;font-size:11px;padding:15px}}.up{{color:var(--up)}}.down{{color:var(--down)}}.muted{{color:var(--muted)}}
@media(max-width:1000px){{.stock-main{{grid-template-columns:34px 1fr 90px 120px 1fr 60px}}.market,.layout2,.detail-columns{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(3,1fr)}}.decision{{grid-template-columns:repeat(2,1fr)}}.quick-grid{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:680px){{.container{{padding:10px}}.header{{display:block}}.meta{{text-align:left;margin-top:8px}}.decision{{grid-template-columns:1fr 1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}.stock-main{{grid-template-columns:28px 1fr 80px}}.score,.badges{{display:none}}.quick-grid{{grid-template-columns:repeat(2,1fr)}}.filters input{{min-width:150px;width:100%}}.count{{margin-left:0;width:100%}}}}
</style>
</head>
<body>
<div class="container">
  <header class="header">
    <div><h1>七因子股票决策仪表盘</h1><div class="sub">{esc(data.get("model", ""))}</div></div>
    <div class="meta"><div>扫描日期：{esc(data.get("scan_date", ""))}</div><div>扫描时间：{esc(data.get("scan_time", ""))}</div><div>系统版本：{esc(data.get("system_version", ""))}</div></div>
  </header>

  <section class="section">
    <div class="section-title">今日决策卡</div>
    <div class="decision">
      <div class="decision-item"><label>市场状态</label><strong>{esc(state)}</strong><div class="muted">情绪 {esc(sent.get("sentiment_score", "-"))}</div></div>
      <div class="decision-item"><label>操作倾向</label><strong>{esc(action)}</strong></div>
      <div class="decision-item"><label>核心关注</label><strong>{esc(focus_text)}</strong></div>
      <div class="decision-item"><label>主要风险</label><strong>{esc(risk)}</strong></div>
      <div class="decision-item"><label>明日验证</label><strong>{esc(validate)}</strong></div>
    </div>
  </section>

  <section class="market">
    <div class="section market-main">
      <div class="section-title">市场情绪</div>
      <div class="state"><span class="dot"></span><div><div class="state-title">{esc(sent.get("sentiment_label", state))}</div><div class="muted">情绪分</div></div><div class="state-score">{esc(sent.get("sentiment_score", "-"))}</div></div>
    </div>
    <div class="section">
      <div class="section-title">关键指标</div>
      <div class="metrics">
        <div class="metric"><span>涨停</span><b class="up">{esc(sent.get("limit_up_count", "-"))}</b></div>
        <div class="metric"><span>跌停</span><b class="down">{esc(sent.get("limit_down_count", "-"))}</b></div>
        <div class="metric"><span>强势股</span><b>{esc(sent.get("strong_count", "-"))}</b></div>
        <div class="metric"><span>炸板率</span><b>{esc(sent.get("explosion_rate", "-"))}%</b></div>
        <div class="metric"><span>最高连板</span><b>{esc(sent.get("max_boards_est", "-"))}</b></div>
        <div class="metric"><span>候选股</span><b>{len(candidates)}</b></div>
      </div>
    </div>
  </section>

  <section class="layout2">
    <div class="section"><div class="section-title">板块强度 TOP10</div><table class="table"><thead><tr><th>#</th><th>板块</th><th>均涨幅</th><th>涨停</th><th>强势</th></tr></thead><tbody>{sector_rows}</tbody></table></div>
    <div class="section"><div class="section-title">热门概念 TOP12</div><div class="concepts">{concept_tags}</div><div class="section-title" style="margin-top:14px">模型配置</div><div class="chips">{pool_html}</div><div class="chips" style="margin-top:7px">{weight_html}</div><div class="chips" style="margin-top:7px">{threshold_html}</div></div>
  </section>

  <section class="section" id="candidateSection">
    <div class="section-title">候选池</div>
    <div class="filters">
      <input id="search" placeholder="搜索股票 / 代码 / 板块" autocomplete="off">
      <select id="pool"><option value="全部">全部</option><option value="重点观察">重点观察</option><option value="预备池">预备池</option><option value="观察池">观察池</option><option value="淘汰">淘汰</option></select>
      <select id="grade"><option value="全部">全部评级</option><option value="A">A级</option><option value="B">B级</option><option value="C">C级</option><option value="D">D级</option></select>
      <select id="sort"><option value="default">推荐排序</option><option value="score">调整分高→低</option><option value="change">涨幅高→低</option><option value="prob">连板概率高→低</option></select>
      <span id="count" class="count"></span>
    </div>
    <div id="stockList" class="stock-list"></div>
    <div id="pagination" class="pagination"></div>
  </section>

  <div class="footer">七因子决策仪表盘 · UI 与数据分离渲染 · 数据仅供研究参考，不构成投资建议</div>
</div>

<script id="app-data" type="application/json">{payload_json}</script>
<script>
const DATA=JSON.parse(document.getElementById('app-data').textContent);
const PAGE_SIZE=50;
let state={{page:1,pool:'全部',grade:'全部',sort:'default',q:'',openCode:''}};
const $=id=>document.getElementById(id);
function E(v){{const d=document.createElement('div');d.textContent=v==null?'-':String(v);return d.innerHTML;}}
function pct(v){{const n=Number(v);return Number.isFinite(n)?(n>=0?'+':'')+n.toFixed(1)+'%':E(v);}}
function pctClass(v){{const n=Number(v);return Number.isFinite(n)?(n>=0?'up':'down'):'muted';}}
function chips(arr,cls='tag'){{const a=Array.isArray(arr)?arr:[];return a.length?a.map(x=>'<span class="tag '+cls+'">'+E(x)+'</span>').join(''):'<span class="tag muted-tag">暂无</span>';}}
function poolClass(v){{return {{'重点观察':'focus','预备池':'ready','观察池':'watch','淘汰':'drop'}}[v]||'drop';}}
function gradeClass(v){{return {{A:'grade-a',B:'grade-b',C:'grade-c',D:'grade-d'}}[v]||'grade-d';}}
function scoreColor(v){{const n=Number(v)||0;return n>=65?'hot':n>=60?'warm':n>=50?'cool':'muted';}}
function factorBlock(s){{const defs=[['个股辨识度',25],['资金预热',20],['K线筹码',15],['题材催化',10],['板块强度',10],['市值流动性',15],['情绪环境',5]];return defs.map(([name,max])=>{{const value=Number(s.factor_scores?.[name]||0);const width=Math.max(0,Math.min(100,value/max*100));return '<div class="factor-row"><div class="factor-head"><span>'+E(name)+'</span><b>'+value.toFixed(1)+'/'+max+'</b></div><div class="factor-bar"><i style="width:'+width.toFixed(0)+'%"></i></div><div class="factor-detail">'+E(s.factor_details?.[name]||'')+'</div></div>';}}).join('');}}
function card(s,index){{const open=s.code===state.openCode;const rc=Number(s.resonance||0);const dots='●'.repeat(rc)+'○'.repeat(Math.max(0,3-rc));const w=Math.max(0,Math.min(100,Number(s.adjusted_total)||0));return '<article class="stock-card '+(open?'open':'')+'"><div class="stock-main"><div class="rank">#'+index+'</div><div><div class="stock-name">'+E(s.name)+' <span>'+E(s.code)+'</span></div><div class="stock-meta"><span>'+E(s.sector||'未分类')+'</span><span>'+E(s.sw_industry||'未分类')+'</span><span>P'+E(s.tier)+'</span></div></div><div class="price"><strong>'+E(s.price)+'</strong><span class="'+pctClass(s.change_pct)+'">'+pct(s.change_pct)+'</span></div><div class="score"><div><b>'+E(s.adjusted_total)+'</b><small>/100</small></div><div class="score-bar"><i class="'+scoreColor(s.adjusted_total)+'" style="width:'+w.toFixed(0)+'%"></i></div><small>原始 '+E(s.scores_total)+'</small></div><div class="badges"><span class="pill '+poolClass(s.pool)+'">'+E(s.pool)+'</span><span class="pill '+gradeClass(s.grade)+'">'+E(s.grade)+'</span><span class="pill tier">'+E(s.tag)+'</span></div><button class="detail-btn" onclick="toggleDetail(\''+E(s.code)+'\')">'+(open?'收起':'展开')+'</button></div><div class="quick-grid"><div><span>三共振</span><b class="resonance">'+dots+'</b><em>'+rc+'/3</em></div><div><span>连板概率</span><b>'+E(s.lianban_probability)+'%</b></div><div><span>涨停历史</span><b>'+E(s.limit_up_count)+'次</b><em>最高'+E(s.max_consecutive)+'连</em></div><div><span>距上次涨停</span><b>'+E(s.days_since_last_lu)+'日</b></div><div><span>换手率</span><b>'+E(s.turnover_rate)+'%</b></div><div><span>流通市值</span><b>'+E(s.circ_mcap_yi)+'亿</b></div></div><div class="watch-row"><label>明日观察</label>'+chips(s.next_day_watch,'watch-tag')+'</div>'+(open?'<div class="stock-detail"><div class="detail-columns"><section><h4>七因子拆解</h4>'+factorBlock(s)+'</section><section><h4>证据摘要</h4><div class="evidence"><div><b>优先级</b><span>'+E(s.tier_label)+' · '+E(s.tag)+'</span></div><div><b>评分来源</b><span>'+E(s.scoring_source)+'</span></div><div><b>近期涨停调整</b><span>'+E(s.recent_adjustment)+'</span></div><div><b>核心概念</b><span>'+E((s.concepts||[]).join(' · ')||'暂无')+'</span></div><div><b>资金信号</b><span>'+E((s.capital_signals||[]).join(' · ')||'暂无')+'</span></div><div><b>K线信号</b><span>'+E((s.kline_signals||[]).join(' · ')||'暂无')+'</span></div></div></section></div></div>':'')+'</article>';}}
function filtered(){{const q=state.q.trim().toLowerCase();let arr=DATA.candidates.filter(s=>{{const hay=(s.name+' '+s.code+' '+(s.sector||'')+' '+(s.sw_industry||'')).toLowerCase();return (state.pool==='全部'||s.pool===state.pool)&&(state.grade==='全部'||s.grade===state.grade)&&(!q||hay.includes(q));}});arr.sort((a,b)=>{{if(state.sort==='score')return Number(b.adjusted_total||0)-Number(a.adjusted_total||0);if(state.sort==='change')return Number(b.change_pct||0)-Number(a.change_pct||0);if(state.sort==='prob')return Number(b.lianban_probability||0)-Number(a.lianban_probability||0);return (Number(a.tier||99)-Number(b.tier||99)) || (Number(b.adjusted_total||0)-Number(a.adjusted_total||0));}});return arr;}}
function renderPages(total){{const pages=Math.max(1,Math.ceil(total/PAGE_SIZE));state.page=Math.min(state.page,pages);let html='';for(let p=1;p<=pages;p++){{if(p===1||p===pages||Math.abs(p-state.page)<=2)html+='<button class="page-btn '+(p===state.page?'active':'')+'" onclick="goPage('+p+')">'+p+'</button>';else if(p===state.page-3||p===state.page+3)html+='<span class="page-info">…</span>';}}$('pagination').innerHTML='<button class="page-btn" onclick="goPage('+Math.max(1,state.page-1)+')">‹</button>'+html+'<button class="page-btn" onclick="goPage('+Math.min(pages,state.page+1)+')">›</button><span class="page-info">'+state.page+' / '+pages+'</span>';}}
function render(){{const arr=filtered();const start=(state.page-1)*PAGE_SIZE;const visible=arr.slice(start,start+PAGE_SIZE);$('count').textContent='显示 '+(arr.length?start+1:0)+'–'+Math.min(start+visible.length,arr.length)+' / '+arr.length+' 只';$('stockList').innerHTML=visible.map((s,i)=>card(s,start+i+1)).join('');renderPages(arr.length);}}
function goPage(p){{state.page=p;state.openCode='';render();document.getElementById('candidateSection').scrollIntoView({{behavior:'smooth',block:'start'}});}}
function toggleDetail(code){{state.openCode=state.openCode===code?'':code;render();}}
$('search').addEventListener('input',e=>{{state.q=e.target.value;state.page=1;state.openCode='';render();}});
$('pool').addEventListener('change',e=>{{state.pool=e.target.value;state.page=1;state.openCode='';render();}});
$('grade').addEventListener('change',e=>{{state.grade=e.target.value;state.page=1;state.openCode='';render();}});
$('sort').addEventListener('change',e=>{{state.sort=e.target.value;state.page=1;state.openCode='';render();}});
render();
</script>
</body></html>'''


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
