#!/usr/bin/env python3
"""GitHub Pages dashboard generator.

把七因子扫描结果从“数据报表”升级成“交易决策仪表盘”：
- 首屏先展示市场状态、今日结论、重点观察池
- 候选股支持关键词 / 池 / 评级 / 优先级筛选与排序
- 每只股票可展开查看七因子、三共振、资金 / K线信号和次日观察项
- 增加概念强度、模型说明与数据时间信息
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


def esc(v):
    return html.escape(str(v if v is not None else "-"))


def pct(v):
    if v is None or v == "-":
        return "-"
    try:
        x = float(v)
    except Exception:
        return esc(v)
    return f"{x:+.1f}%"


def pct_class(v):
    try:
        return "up" if float(v) >= 0 else "down"
    except Exception:
        return "muted"


def pool_class(pool):
    return {"重点观察": "focus", "预备池": "ready", "观察池": "watch", "淘汰": "drop"}.get(pool, "muted")


def grade_class(g):
    return {"A": "a", "B": "b", "C": "c", "D": "d"}.get(g, "d")


def risk_label(sent):
    score = sent.get("sentiment_score")
    label = sent.get("sentiment_label", "-")
    try:
        s = float(score)
    except Exception:
        return label, "neutral"
    if s >= 70:
        return label, "hot"
    if s >= 55:
        return label, "warm"
    if s < 40:
        return label, "cold"
    return label, "neutral"


def factor_rows(scores, details):
    factors = [
        ("个股辨识度", 25, scores.get("stock_recognition", 0)),
        ("资金预热", 20, scores.get("capital_preheat", 0)),
        ("K线筹码", 15, scores.get("kline_chip", 0)),
        ("题材催化", 10, scores.get("theme_catalyst", 0)),
        ("板块强度", 10, scores.get("sector_strength", 0)),
        ("市值流动性", 15, scores.get("market_cap_liquidity", 0)),
        ("情绪环境", 5, scores.get("sentiment", 0)),
    ]
    rows = []
    for name, max_score, val in factors:
        try:
            width = max(0, min(100, float(val) / max_score * 100))
            val_text = f"{float(val):.1f}"
        except Exception:
            width = 0
            val_text = "-"
        detail = details.get(name + f"(/{max_score})", details.get(name, ""))
        rows.append(f"<div class='factor'><div class='factor-head'><span>{esc(name)}</span><b>{val_text}/{max_score}</b></div><div class='bar'><i style='width:{width:.0f}%'></i></div><div class='factor-detail'>{esc(detail)}</div></div>")
    return "".join(rows)


def signal_tags(items, tone="default"):
    if not items:
        return "<span class='tag muted-tag'>暂无信号</span>"
    return "".join(f"<span class='tag {tone}'>{esc(x)}</span>" for x in items[:8])


def stock_card(r, idx):
    pool = r.get("pool", "-")
    grade = r.get("grade", "-")
    score = r.get("adjusted_total", 0)
    rec = r.get("recency", {})
    hist = r.get("history", {})
    res = r.get("resonance", {})
    scores = r.get("scores", {})
    details = r.get("score_details", {})
    concepts = r.get("all_concepts", [])
    watch = r.get("next_day_watch", [])
    cap = r.get("capital_signals", [])
    kl = r.get("kline_signals", [])
    resonance_count = res.get("count", 0)
    try:
        score_width = max(0, min(100, float(score)))
    except Exception:
        score_width = 0
    resonance = "●" * int(resonance_count) + "○" * max(0, 3 - int(resonance_count))
    return f"""
    <article class='stock-card' data-pool='{esc(pool)}' data-grade='{esc(grade)}' data-tier='{esc(rec.get('tier_label',''))}' data-name='{esc(r.get('name',''))} {esc(r.get('code',''))} {esc(r.get('sector',''))}'>
      <div class='stock-top'>
        <div class='rank'>#{idx}</div>
        <div class='identity'>
          <div class='stock-name'>{esc(r.get('name'))} <span>{esc(r.get('code'))}</span></div>
          <div class='stock-meta'><span>{esc(r.get('sector','未分类'))}</span><span>{esc(r.get('sw_industry','未分类'))}</span><span>{esc(r.get('recency',{}).get('tag','-'))}</span></div>
        </div>
        <div class='price-box'><strong>{esc(r.get('price'))}</strong><span class='{pct_class(r.get('change_pct'))}'>{pct(r.get('change_pct'))}</span></div>
        <div class='score-box'><div><b>{esc(score)}</b><span> / 100</span></div><div class='score-line'><i style='width:{score_width:.0f}%'></i></div><small>原始 {esc(scores.get('total','-'))}</small></div>
        <div class='labels'><span class='pill {pool_class(pool)}'>{esc(pool)}</span><span class='pill grade-{grade_class(grade)}'>{esc(grade)}</span><span class='pill tier'>{esc(rec.get('tier_label','-'))}</span></div>
        <button class='detail-btn' onclick='toggleDetail(this)'>展开详情</button>
      </div>

      <div class='quick-grid'>
        <div><span>三共振</span><b class='resonance'>{resonance}</b><em>{resonance_count}/3</em></div>
        <div><span>连板概率</span><b>{esc(r.get('lianban_probability','-'))}%</b></div>
        <div><span>涨停历史</span><b>{esc(hist.get('limit_up_count','-'))}次</b><em>最高{esc(hist.get('max_consecutive','-'))}连</em></div>
        <div><span>距上次涨停</span><b>{esc(hist.get('days_since_last_lu','-'))}日</b></div>
        <div><span>换手率</span><b>{esc(r.get('turnover_rate','-'))}%</b></div>
        <div><span>流通市值</span><b>{esc(r.get('circ_mcap_yi','-'))}亿</b></div>
      </div>

      <div class='signal-row'><div><label>明日关注</label>{signal_tags(watch, 'watch-tag')}</div><div><label>资金</label>{signal_tags(cap, 'capital-tag')}</div><div><label>K线</label>{signal_tags(kl, 'k-tag')}</div></div>

      <div class='stock-detail'>
        <div class='detail-columns'>
          <section><h4>七因子拆解</h4>{factor_rows(scores, details)}</section>
          <section><h4>为什么进入这个池</h4><div class='reason-box'><div><b>优先级</b><span>{esc(rec.get('tier_label','-'))} · {esc(rec.get('tag','-'))}</span></div><div><b>评分来源</b><span>{'概念板块' if r.get('scoring_source') == 'concept' else '申万行业'}</span></div><div><b>近期调整</b><span>{esc(details.get('近期涨停调整','0'))}</span></div><div><b>核心概念</b><span>{esc(', '.join(concepts[:5]) if concepts else r.get('concept') or '无')}</span></div></div><div class='next-plan'><b>次日观察重点</b>{signal_tags(watch, 'watch-tag')}</div></section>
        </div>
      </div>
    </article>"""


def generate_html(data):
    version = data.get("system_version", "")
    model = data.get("model", "")
    scan_date = data.get("scan_date", "")
    scan_time = data.get("scan_time", "")
    sent = data.get("market_sentiment", {})
    summary = data.get("summary", {})
    candidates = data.get("candidates", [])
    sectors = data.get("sector_rankings", [])[:8]
    concepts = data.get("concept_rankings", [])[:10]
    weights = data.get("weight_config", {})
    threshold = data.get("threshold", {})

    pool_order = {"重点观察": 0, "预备池": 1, "观察池": 2, "淘汰": 3}
    ranked = sorted(candidates, key=lambda x: (pool_order.get(x.get("pool"), 9), x.get("recency", {}).get("tier", 99), -x.get("adjusted_total", 0)))
    focus = [r for r in ranked if r.get("pool") == "重点观察"]
    ready = [r for r in ranked if r.get("pool") == "预备池"]
    label, mood_cls = risk_label(sent)

    factor_config = "".join(f"<span><b>{esc(k)}</b>{esc(v)}分</span>" for k, v in weights.items())
    threshold_config = "".join(f"<span><b>{esc(k)}</b>{esc(v)}</span>" for k, v in threshold.items())
    sector_rows = "".join(f"<tr><td>{s.get('rank')}</td><td>{esc(s.get('name'))}</td><td class='{pct_class(s.get('avg_change'))}'>{pct(s.get('avg_change'))}</td><td>{esc(s.get('limit_up_count'))}</td><td>{esc(s.get('strong_count'))}</td></tr>" for s in sectors)
    concept_tags = "".join(f"<span class='concept-tag'><b>{esc(c.get('rank'))}</b> {esc(c.get('name'))} <em>{pct(c.get('avg_change'))}</em></span>" for c in concepts)
    cards = "".join(stock_card(r, i + 1) for i, r in enumerate(ranked))

    total = summary.get("total_scanned", len(candidates))
    failed = summary.get("total_failed", 0)
    pool_dist = summary.get("pool_distribution", {})

    return f"""<!DOCTYPE html>
<html lang='zh-CN'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'>
<title>七因子决策仪表盘 {esc(version)}</title>
<style>
:root{{--bg:#0b0e13;--panel:#141922;--panel2:#1a202b;--line:#293140;--text:#e8edf5;--muted:#8590a3;--accent:#5b9cff;--up:#ff5c6c;--down:#35c98b;--gold:#f6c453;--orange:#ff9e43;--shadow:0 10px 30px rgba(0,0,0,.18)}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top,#121823 0,#0b0e13 45%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;font-size:14px}}
.container{{max-width:1500px;margin:auto;padding:22px}}.hero{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:18px}}h1{{margin:0;font-size:27px;letter-spacing:-.5px}}.sub{{color:var(--muted);margin-top:7px;font-size:13px}}.meta{{text-align:right;color:var(--muted);font-size:12px;line-height:1.8}}
.market{{display:grid;grid-template-columns:1.2fr 2fr;gap:14px;margin-bottom:14px}}.panel{{background:rgba(20,25,34,.92);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}}.market-main{{padding:18px}}.market-state{{display:flex;align-items:center;gap:15px}}.state-dot{{width:12px;height:12px;border-radius:50%;background:var(--accent);box-shadow:0 0 14px rgba(91,156,255,.45)}}.state-dot.hot{{background:var(--up);box-shadow:0 0 14px rgba(255,92,108,.4)}}.state-dot.warm{{background:var(--orange)}}.state-dot.cold{{background:var(--down)}}.state-title{{font-size:21px;font-weight:800}}.state-score{{font-size:36px;font-weight:900;line-height:1}}.state-desc{{color:var(--muted);font-size:12px;margin-top:8px}}.metric-grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-top:18px}}.metric{{background:var(--panel2);padding:10px;border-radius:10px}}.metric span,.quick-grid span{{display:block;color:var(--muted);font-size:11px;margin-bottom:6px}}.metric b{{font-size:18px}}
.actions{{padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:10px}}.action-card{{padding:13px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(180deg,#1b212c,#151a23)}}.action-card .big{{font-size:24px;font-weight:900}}.action-card .hint{{font-size:11px;color:var(--muted);margin-top:4px}}.action-focus{{border-color:rgba(255,92,108,.3);background:linear-gradient(180deg,rgba(88,33,42,.32),#151a23)}}.action-ready{{border-color:rgba(255,158,67,.3);background:linear-gradient(180deg,rgba(82,54,28,.3),#151a23)}}
.section{{margin-bottom:14px;padding:16px}}.section-head{{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}}.title{{font-size:16px;font-weight:800}}.hint{{color:var(--muted);font-size:12px}}.layout2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.table{{width:100%;border-collapse:collapse}}.table th,.table td{{padding:8px 7px;text-align:left;border-bottom:1px solid var(--line);font-size:12px}}.table th{{color:var(--muted);font-weight:600}}.up{{color:var(--up)}.down{{color:var(--down)}.muted{{color:var(--muted)}}
.concepts{{display:flex;flex-wrap:wrap;gap:7px}}.concept-tag{{padding:7px 9px;background:var(--panel2);border:1px solid var(--line);border-radius:9px;font-size:12px}}.concept-tag b{{color:var(--gold);margin-right:3px}}.concept-tag em{{font-style:normal;margin-left:7px}}
.filters{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}input,select{{background:#0f141c;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:8px 10px;outline:none}}input{{min-width:220px}}.filter-btn{{background:#111720;color:var(--muted);border:1px solid var(--line);padding:8px 10px;border-radius:9px;cursor:pointer}}.filter-btn.active{{background:rgba(91,156,255,.14);border-color:rgba(91,156,255,.4);color:#bcd4ff}}.count{{margin-left:auto;color:var(--muted);font-size:12px}}
.stock-list{{display:flex;flex-direction:column;gap:10px}}.stock-card{{background:rgba(20,25,34,.92);border:1px solid var(--line);border-radius:13px;overflow:hidden}}.stock-top{{display:grid;grid-template-columns:42px minmax(230px,1.3fr) 110px 150px 220px 80px;gap:12px;align-items:center;padding:13px 14px}}.rank{{color:var(--muted);font-weight:700}}.stock-name{{font-weight:800;font-size:16px}}.stock-name span{{color:var(--muted);font-size:11px;font-weight:500;margin-left:5px}}.stock-meta{{display:flex;flex-wrap:wrap;gap:7px;margin-top:5px;color:var(--muted);font-size:11px}}.stock-meta span{{padding:2px 6px;background:#0f141c;border-radius:5px}}.price-box strong{{display:block;font-size:18px}}.price-box span{{font-weight:700}}.score-box b{{font-size:21px}}.score-box span,.score-box small{{color:var(--muted);font-size:11px}}.score-line,.bar{{height:5px;background:#2b3340;border-radius:8px;overflow:hidden}}.score-line i,.bar i{{display:block;height:100%;background:linear-gradient(90deg,#477ddf,#8db5ff);border-radius:8px}}.labels{display:flex;flex-wrap:wrap;gap:5px}.pill{display:inline-flex;align-items:center;padding:5px 8px;border-radius:7px;font-size:11px;border:1px solid transparent}.focus{background:rgba(255,92,108,.13);color:#ff93a0;border-color:rgba(255,92,108,.25)}.ready{background:rgba(255,158,67,.12);color:#ffc17b;border-color:rgba(255,158,67,.25)}.watch{background:rgba(91,156,255,.12);color:#a9c9ff;border-color:rgba(91,156,255,.24)}.drop{background:#1d232c;color:var(--muted)}.tier{background:#171d27;border-color:var(--line);color:#b8c2d1}.grade-a{background:rgba(255,92,108,.12);color:#ff93a0}.grade-b{background:rgba(255,158,67,.12);color:#ffc17b}.grade-c{background:rgba(91,156,255,.12);color:#a9c9ff}.grade-d{background:#1d232c;color:var(--muted)}.detail-btn{border:1px solid var(--line);background:#10161f;color:var(--muted);border-radius:8px;padding:7px 8px;cursor:pointer}.detail-btn:hover{color:var(--text);border-color:#41506a}
.quick-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;padding:0 14px 12px}.quick-grid>div{background:#10161f;border:1px solid #212a36;border-radius:9px;padding:9px}.quick-grid b{display:inline-block;font-size:14px}.quick-grid em{font-size:10px;color:var(--muted);font-style:normal;margin-left:5px}.resonance{color:var(--gold);letter-spacing:1px}
.signal-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px;padding:0 14px 13px}.signal-row>div{background:#10161f;border:1px solid #212a36;padding:9px;border-radius:9px}.signal-row label{display:block;color:var(--muted);font-size:10px;margin-bottom:5px}.tag{display:inline-block;background:#1d2430;border:1px solid #2a3443;border-radius:6px;padding:3px 6px;font-size:10px;margin:2px;color:#bac5d5}.watch-tag{color:#d9e5ff;border-color:#314b73;background:rgba(91,156,255,.11)}.capital-tag{color:#d2f3e3;border-color:#285444;background:rgba(53,201,139,.10)}.k-tag{color:#ffe8b8;border-color:#5b4723;background:rgba(246,196,83,.08)}.muted-tag{color:var(--muted)}
.stock-detail{display:none;border-top:1px solid var(--line);padding:14px;background:#10151d}.stock-card.open .stock-detail{display:block}.stock-card.open .detail-btn{color:#d7e5ff;border-color:#35517e}.detail-columns{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}.detail-columns section{background:#131a24;border:1px solid #232d3b;border-radius:10px;padding:13px}.detail-columns h4{margin:0 0 10px;font-size:13px}.factor{margin:9px 0}.factor-head{display:flex;justify-content:space-between;font-size:11px}.factor-head b{font-size:11px}.factor-detail{font-size:10px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.reason-box{display:grid;grid-template-columns:1fr 1fr;gap:8px}.reason-box>div{background:#0f141c;border:1px solid #202a36;border-radius:8px;padding:9px}.reason-box b,.next-plan>b{display:block;font-size:10px;color:var(--muted);margin-bottom:5px}.reason-box span{font-size:11px}.next-plan{margin-top:9px;background:#0f141c;border:1px solid #202a36;border-radius:8px;padding:9px}
.config{{margin-top:4px}}.config-line{display:flex;flex-wrap:wrap;gap:7px}.chip{padding:5px 8px;background:#10161f;border:1px solid var(--line);border-radius:7px;font-size:11px;color:var(--muted)}.chip b{color:#cbd6e6;margin-right:4px}.footer{text-align:center;color:#566173;font-size:11px;padding:18px 0 8px}
@media(max-width:1000px){{.market,.layout2,.detail-columns{{grid-template-columns:1fr}}.stock-top{{grid-template-columns:34px 1fr 90px 120px}.labels,.detail-btn{{grid-column:auto}}.stock-top .score-box{{order:5}.stock-top .labels{{order:4}.detail-btn{{order:6}}.quick-grid{{grid-template-columns:repeat(3,1fr)}}.signal-row{{grid-template-columns:1fr}}.metric-grid{{grid-template-columns:repeat(4,1fr)}}}}
@media(max-width:640px){{.container{{padding:12px}}.hero{{align-items:flex-start;flex-direction:column}}.meta{{text-align:left}}.metric-grid{{grid-template-columns:repeat(2,1fr)}}.stock-top{{grid-template-columns:26px 1fr 80px}}.price-box{{text-align:right}}.score-box,.labels,.detail-btn{{grid-column:2 / -1}}.quick-grid{{grid-template-columns:repeat(2,1fr)}}input{{min-width:160px;width:100%}}.count{{width:100%;margin-left:0}}}}
</style></head>
<body>
<div class='container'>
  <header class='hero'><div><h1>七因子股票决策仪表盘</h1><div class='sub'>{esc(model)}</div></div><div class='meta'>扫描日期：{esc(scan_date)}<br>扫描时间：{esc(scan_time)} · 数据源：新浪财经 API</div></header>

  <section class='market'>
    <div class='panel market-main'><div class='market-state'><span class='state-dot {mood_cls}'></span><div><div class='state-title'>{esc(label)}</div><div class='state-desc'>今天先看市场环境，再看个股。分数不是买入指令，重点是识别“值得继续跟踪”的候选。</div></div><div style='margin-left:auto;text-align:right'><div class='state-score'>{esc(sent.get('sentiment_score','-'))}</div><div class='state-desc'>情绪分</div></div></div><div class='metric-grid'>
      <div class='metric'><span>涨停</span><b class='up'>{esc(sent.get('limit_up_count','-'))}</b></div><div class='metric'><span>跌停</span><b class='down'>{esc(sent.get('limit_down_count','-'))}</b></div><div class='metric'><span>强势股</span><b>{esc(sent.get('strong_count','-'))}</b></div><div class='metric'><span>炸板率</span><b>{esc(sent.get('explosion_rate','-'))}%</b></div><div class='metric'><span>最高连板</span><b>{esc(sent.get('max_boards_est','-'))}</b></div><div class='metric'><span>冰点状态</span><b>{'是' if sent.get('is_ice_point') else '否'}</b></div><div class='metric'><span>候选总数</span><b>{esc(total)}</b></div>
    </div></div>
    <div class='panel actions'><div class='action-card action-focus'><div class='hint'>重点观察</div><div class='big'>{esc(pool_dist.get('重点观察', len(focus)))}只</div><div class='hint'>≥65分 + 三共振，优先继续跟踪</div></div><div class='action-card action-ready'><div class='hint'>预备池</div><div class='big'>{esc(pool_dist.get('预备池', len(ready)))}只</div><div class='hint'>接近阈值，等待强度或资金进一步确认</div></div><div class='action-card'><div class='hint'>观察池</div><div class='big'>{esc(pool_dist.get('观察池', 0))}只</div><div class='hint'>只做观察，不作为首选</div></div><div class='action-card'><div class='hint'>失败记录</div><div class='big'>{esc(failed)}</div><div class='hint'>扫描异常，不等同于淘汰</div></div></div>
  </section>

  <section class='panel section'><div class='section-head'><div><div class='title'>热点与板块</div><div class='hint'>先找市场共识，再看个股质量</div></div></div><div class='layout2'><div><table class='table'><thead><tr><th>#</th><th>行业</th><th>均涨幅</th><th>涨停</th><th>强势</th></tr></thead><tbody>{sector_rows}</tbody></table></div><div><div class='hint' style='margin-bottom:7px'>概念强度 TOP10</div><div class='concepts'>{concept_tags or '<span class="muted">暂无概念数据</span>'}</div></div></div></section>

  <section class='panel section config'><div class='section-head'><div><div class='title'>模型配置</div><div class='hint'>把“模型怎么算”与“今天看什么”分开，避免首屏被参数淹没</div></div></div><div class='config-line'>{factor_config}</div><div class='config-line' style='margin-top:7px'>{threshold_config}</div></section>

  <section class='section'><div class='section-head'><div><div class='title'>候选池</div><div class='hint'>按“池 → 优先级 → 调整分”排序；点击展开看证据链</div></div><div class='count' id='count'></div></div><div class='filters'><input id='search' placeholder='搜索股票 / 代码 / 板块'><select id='sort'><option value='score'>调整分从高到低</option><option value='recency'>优先级优先</option><option value='change'>今日涨幅</option><option value='prob'>连板概率</option></select><button class='filter-btn active' data-pool='全部'>全部</button><button class='filter-btn' data-pool='重点观察'>重点观察</button><button class='filter-btn' data-pool='预备池'>预备池</button><button class='filter-btn' data-pool='观察池'>观察池</button><select id='grade'><option value='全部'>全部评级</option><option value='A'>A</option><option value='B'>B</option><option value='C'>C</option><option value='D'>D</option></select></div></section>
  <div class='stock-list' id='stockList'>{cards}</div>
  <div class='footer'>七因子选股系统 {esc(version)} · 每工作日 15:35 自动更新 · 数据仅供研究参考，不构成投资建议</div>
</div>
<script>
const cards=[...document.querySelectorAll('.stock-card')];let pool='全部';
function toggleDetail(btn){{const c=btn.closest('.stock-card');c.classList.toggle('open');btn.textContent=c.classList.contains('open')?'收起详情':'展开详情'}}
function num(v){{const x=parseFloat(v);return isNaN(x)?-99999:x}}
function render(){{const q=document.getElementById('search').value.trim().toLowerCase(),g=document.getElementById('grade').value,s=document.getElementById('sort').value;let visible=cards.filter(c=>{{const okPool=pool==='全部'||c.dataset.pool===pool;const okGrade=g==='全部'||c.dataset.grade===g;const okQ=!q||c.dataset.name.toLowerCase().includes(q);return okPool&&okGrade&&okQ}});visible.sort((a,b)=>{{if(s==='recency')return a.dataset.tier.localeCompare(b.dataset.tier,'zh');if(s==='change')return num(b.querySelector('.price-box span').textContent)-num(a.querySelector('.price-box span').textContent);if(s==='prob')return num(b.querySelector('.quick-grid div:nth-child(2) b').textContent)-num(a.querySelector('.quick-grid div:nth-child(2) b').textContent);return num(b.querySelector('.score-box b').textContent)-num(a.querySelector('.score-box b').textContent)}});cards.forEach(c=>c.style.display='none');visible.forEach(c=>{{c.style.display='block';document.getElementById('stockList').appendChild(c)}});document.getElementById('count').textContent=`显示 ${{visible.length}} / ${{cards.length}} 只`;}}
document.getElementById('search').addEventListener('input',render);document.getElementById('sort').addEventListener('change',render);document.getElementById('grade').addEventListener('change',render);document.querySelectorAll('.filter-btn').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');pool=b.dataset.pool;render()}}));render();
</script></body></html>"""


def write_page(html_text):
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_text)


def run():
    data = load_data()
    html_text = generate_html(data)
    write_page(html_text)
    print(f"[Pages] 决策仪表盘已生成：{OUTPUT_HTML}（{len(html_text)} 字节）")
    return {"output": OUTPUT_HTML, "size": len(html_text)}


if __name__ == '__main__':
    run()
