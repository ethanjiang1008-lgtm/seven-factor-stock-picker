#!/usr/bin/env python3
"""
GitHub Pages 网页生成模块 — 连板潜力七因子选股系统
只负责读取 data/seven_factor_latest.json 并生成 docs/index.html。
选股、评分、数据抓取等逻辑不在此文件中。
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
    return html.escape(str(value if value is not None else "-"))


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


def score_color(score):
    try:
        s = float(score)
    except Exception:
        s = 0
    if s >= 65:
        return "hot"
    if s >= 60:
        return "warm"
    if s >= 50:
        return "cool"
    return "muted"


def pool_class(pool):
    return {
        "重点观察": "focus",
        "预备池": "ready",
        "观察池": "watch",
        "淘汰": "drop",
    }.get(pool, "drop")


def grade_class(grade):
    return {
        "A": "grade-a",
        "B": "grade-b",
        "C": "grade-c",
        "D": "grade-d",
    }.get(grade, "grade-d")


def safe_join(values, limit=5):
    if not values:
        return "暂无"
    if isinstance(values, str):
        return values
    if isinstance(values, dict):
        parts = []
        for key, value in values.items():
            if isinstance(value, (list, tuple, set)):
                parts.extend(f"{key}: {x}" for x in list(value)[:limit])
            else:
                parts.append(f"{key}: {value}")
        return " · ".join(str(x) for x in parts[:limit]) or "暂无"
    try:
        return " · ".join(str(x) for x in list(values)[:limit]) or "暂无"
    except TypeError:
        return str(values)


def chips(values, cls="tag"):
    if not values:
        return '<span class="tag muted-tag">暂无</span>'
    if isinstance(values, str):
        values = [values]
    elif isinstance(values, dict):
        values = [f"{k}: {v}" for k, v in values.items()]
    else:
        try:
            values = list(values)
        except TypeError:
            values = [str(values)]
    return "".join(
        f'<span class="tag {cls}">{esc(value)}</span>' for value in values[:8]
    )


def factor_rows(stock):
    scores = stock.get("scores", {}) or {}
    details = stock.get("score_details", {}) or {}
    factors = [
        ("个股辨识度", 25, "stock_recognition"),
        ("资金预热", 20, "capital_preheat"),
        ("K线筹码", 15, "kline_chip"),
        ("题材催化", 10, "theme_catalyst"),
        ("板块强度", 10, "sector_strength"),
        ("市值流动性", 15, "market_cap_liquidity"),
        ("情绪环境", 5, "sentiment"),
    ]
    rows = []
    for name, max_score, key in factors:
        try:
            value = float(scores.get(key, 0))
        except Exception:
            value = 0
        width = max(0, min(100, value / max_score * 100))
        detail = details.get(f"{name}(/{max_score})", details.get(name, ""))
        rows.append(
            f"""
            <div class="factor-row">
              <div class="factor-head"><span>{esc(name)}</span><b>{value:.1f}/{max_score}</b></div>
              <div class="factor-bar"><i style="width:{width:.0f}%"></i></div>
              <div class="factor-detail">{esc(detail)}</div>
            </div>
            """
        )
    return "".join(rows)


def stock_card(stock, index):
    pool = stock.get("pool", "-")
    grade = stock.get("grade", "-")
    score = stock.get("adjusted_total", 0)
    recency = stock.get("recency", {}) or {}
    history = stock.get("history", {}) or {}
    resonance = stock.get("resonance", {}) or {}
    concepts = stock.get("all_concepts", []) or []

    try:
        score_width = max(0, min(100, float(score)))
    except Exception:
        score_width = 0

    rc = int(resonance.get("count", 0) or 0)
    resonance_text = "●" * rc + "○" * max(0, 3 - rc)

    return f"""
    <article class="stock-card"
      data-pool="{esc(pool)}"
      data-grade="{esc(grade)}"
      data-tier="{esc(recency.get('tier', 99))}"
      data-name="{esc(stock.get('name', ''))} {esc(stock.get('code', ''))} {esc(stock.get('sector', ''))}">
      <div class="stock-main">
        <div class="rank">#{index}</div>
        <div class="stock-title">
          <div class="stock-name">{esc(stock.get('name'))} <span>{esc(stock.get('code'))}</span></div>
          <div class="stock-meta">
            <span>{esc(stock.get('sector', '未分类'))}</span>
            <span>{esc(stock.get('sw_industry', '未分类'))}</span>
            <span>P{esc(recency.get('tier', '-'))}</span>
          </div>
        </div>
        <div class="price">
          <strong>{esc(stock.get('price'))}</strong>
          <span class="{pct_cls(stock.get('change_pct'))}">{pct(stock.get('change_pct'))}</span>
        </div>
        <div class="score">
          <div><b>{esc(score)}</b><small>/100</small></div>
          <div class="score-bar"><i class="{score_color(score)}" style="width:{score_width:.0f}%"></i></div>
          <small>原始 {esc(stock.get('scores', {}).get('total', '-'))}</small>
        </div>
        <div class="badges">
          <span class="pill {pool_class(pool)}">{esc(pool)}</span>
          <span class="pill {grade_class(grade)}">{esc(grade)}</span>
          <span class="pill tier">{esc(recency.get('tag', '-'))}</span>
        </div>
        <button class="detail-btn" type="button" onclick="toggleDetail(this)">展开</button>
      </div>

      <div class="quick-grid">
        <div><span>三共振</span><b class="resonance">{resonance_text}</b><em>{rc}/3</em></div>
        <div><span>连板概率</span><b>{esc(stock.get('lianban_probability', '-'))}%</b></div>
        <div><span>涨停历史</span><b>{esc(history.get('limit_up_count', '-'))}次</b><em>最高{esc(history.get('max_consecutive', '-'))}连</em></div>
        <div><span>距上次涨停</span><b>{esc(history.get('days_since_last_lu', '-'))}日</b></div>
        <div><span>换手率</span><b>{esc(stock.get('turnover_rate', '-'))}%</b></div>
        <div><span>流通市值</span><b>{esc(stock.get('circ_mcap_yi', '-'))}亿</b></div>
      </div>

      <div class="watch-row">
        <div><label>明日观察</label>{chips(stock.get('next_day_watch'), 'watch-tag')}</div>
      </div>

      <div class="stock-detail">
        <div class="detail-columns">
          <section>
            <h4>七因子拆解</h4>
            {factor_rows(stock)}
          </section>
          <section>
            <h4>证据摘要</h4>
            <div class="evidence">
              <div><b>优先级</b><span>{esc(recency.get('tier_label', '-'))} · {esc(recency.get('tag', '-'))}</span></div>
              <div><b>评分来源</b><span>{esc('概念板块' if stock.get('scoring_source') == 'concept' else '申万行业')}</span></div>
              <div><b>近期涨停调整</b><span>{esc(stock.get('score_details', {}).get('近期涨停调整', 0))}</span></div>
              <div><b>核心概念</b><span>{esc(safe_join(concepts))}</span></div>
            </div>
          </section>
        </div>
      </div>
    </article>
    """


def generate_html(data):
    sent = data.get("market_sentiment", {}) or {}
    summary = data.get("summary", {}) or {}
    candidates = data.get("candidates", []) or []
    sectors = data.get("sector_rankings", [])[:10]
    concepts = data.get("concept_rankings", [])[:10]

    score = float(sent.get("sentiment_score", 50) or 50)
    if score >= 70:
        state, action = "强势", "进攻优先"
    elif score >= 55:
        state, action = "偏强", "精选参与"
    elif score >= 40:
        state, action = "震荡", "控制仓位"
    else:
        state, action = "偏弱", "防守观察"

    ranked = sorted(
        candidates,
        key=lambda x: (
            {"重点观察": 0, "预备池": 1, "观察池": 2, "淘汰": 3}.get(x.get("pool"), 9),
            x.get("recency", {}).get("tier", 99),
            -float(x.get("adjusted_total", 0) or 0),
        ),
    )

    focus = [x for x in ranked if x.get("pool") == "重点观察"][:3]
    focus_text = " · ".join(
        f"{x.get('name', '-')} {x.get('adjusted_total', '-')}" for x in focus
    ) or "暂无"
    risk = "炸板率较高，强势股分化需要验证" if float(sent.get("explosion_rate", 0) or 0) >= 20 else "高位股仍需关注次日承接"
    validate = "观察核心候选是否继续放量、保持趋势并形成题材共振"

    sector_rows = "".join(
        f"<tr><td>{esc(s.get('rank'))}</td><td>{esc(s.get('name'))}</td>"
        f"<td class='{pct_cls(s.get('avg_change'))}'>{pct(s.get('avg_change'))}</td>"
        f"<td>{esc(s.get('limit_up_count'))}</td><td>{esc(s.get('strong_count'))}</td></tr>"
        for s in sectors
    )
    concept_tags = "".join(
        f"<span class='concept-tag'><b>{esc(c.get('rank'))}</b>{esc(c.get('name'))}"
        f"<em>{pct(c.get('avg_change'))}</em></span>"
        for c in concepts
    )
    cards = "".join(stock_card(stock, i + 1) for i, stock in enumerate(ranked))

    pool_dist = summary.get("pool_distribution", {}) or {}
    pool_html = "".join(
        f'<span class="concept-tag">{esc(k)} <em>{esc(v)}只</em></span>'
        for k, v in pool_dist.items()
    )
    weight_html = "".join(
        f'<span class="concept-tag">{esc(k)} <em>{esc(v)}分</em></span>'
        for k, v in data.get("weight_config", {}).items()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>七因子股票决策仪表盘 {esc(data.get('system_version', ''))}</title>
<style>
:root{{--bg:#0b0f14;--panel:#121821;--panel2:#171f2a;--line:#25303d;--text:#edf2f7;--muted:#7f8b9c;--blue:#5b9cff;--up:#ff6675;--down:#35c98b;--gold:#f6c453;--orange:#ff9f43}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px}}
.container{{max-width:1500px;margin:auto;padding:20px}}
.header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:16px}}
h1{{margin:0;font-size:28px}} .sub{{margin-top:7px;color:var(--muted);font-size:13px}} .meta{{text-align:right;color:var(--muted);font-size:12px;line-height:1.8}}
.section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}}
.section-title{{font-size:16px;font-weight:800;margin-bottom:12px}}
.decision{{display:grid;grid-template-columns:1.25fr 1fr 1fr 1fr 1.45fr;gap:8px}}
.decision-item{{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:13px}}
.decision-item label{{display:block;color:var(--muted);font-size:11px;margin-bottom:7px}} .decision-item strong{{font-size:17px}}
.market{{display:grid;grid-template-columns:1.2fr 2fr;gap:12px}}
.market-main{{padding:16px}} .state{{display:flex;align-items:center;gap:12px}} .dot{{width:12px;height:12px;border-radius:50%;background:var(--blue)}} .state-score{{font-size:38px;font-weight:900}}
.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:16px}}
.metric{{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:10px}} .metric span{{display:block;color:var(--muted);font-size:11px;margin-bottom:4px}} .metric b{{font-size:18px}}
.up{{color:var(--up)}} .down{{color:var(--down)}} .muted{{color:var(--muted)}}
.layout2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.table{{width:100%;border-collapse:collapse}} .table th,.table td{{padding:8px;border-bottom:1px solid var(--line);font-size:12px;text-align:left}} .table th{{color:var(--muted)}}
.concepts{{display:flex;flex-wrap:wrap;gap:7px}} .concept-tag{{padding:7px 9px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;font-size:12px}} .concept-tag b{{color:var(--gold);margin-right:4px}} .concept-tag em{{margin-left:7px;font-style:normal;color:var(--muted)}}
.filters{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}} .filters input,.filters select,.filter-btn{{background:#0e141b;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:8px 10px}} .filters input{{min-width:230px}} .filter-btn{{cursor:pointer;color:var(--muted)}} .filter-btn.active{{border-color:#466eaa;background:#15233a;color:#c8dcff}}
.count{{margin-left:auto;color:var(--muted);font-size:12px}}
.stock-list{{display:flex;flex-direction:column;gap:10px}}
.stock-card{{background:var(--panel);border:1px solid var(--line);border-radius:13px;overflow:hidden}}
.stock-main{{display:grid;grid-template-columns:40px minmax(220px,1.4fr) 110px 150px 220px 75px;gap:12px;align-items:center;padding:13px 14px}}
.rank{{color:var(--muted);font-weight:700}} .stock-name{{font-size:16px;font-weight:800}} .stock-name span{{font-size:11px;color:var(--muted)}} .stock-meta{{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;font-size:11px;color:var(--muted)}} .stock-meta span{{background:#0e141b;padding:2px 6px;border-radius:5px}}
.price strong{{display:block;font-size:18px}} .price span{{font-weight:700}}
.score b{{font-size:21px}} .score small{{display:block;color:var(--muted);font-size:11px}} .score-bar,.factor-bar{{height:5px;background:#2a3440;border-radius:8px;overflow:hidden;margin:5px 0}} .score-bar i,.factor-bar i{{display:block;height:100%}} .score-bar i.hot,.factor-bar i{{background:var(--blue)}} .score-bar i.warm{{background:var(--orange)}} .score-bar i.cool{{background:#7aa7dd}} .score-bar i.muted{{background:#5b6572}}
.badges{{display:flex;flex-wrap:wrap;gap:5px}} .pill{{padding:5px 8px;border-radius:7px;font-size:11px;border:1px solid transparent}} .focus{{background:#3c1d24;color:#ff9ca8}} .ready{{background:#3a2918;color:#ffc37e}} .watch{{background:#162b47;color:#a7c8ff}} .drop,.grade-d{{background:#1c232c;color:var(--muted)}} .grade-a{{background:#3c1d24;color:#ff9ca8}} .grade-b{{background:#3a2918;color:#ffc37e}} .grade-c{{background:#162b47;color:#a7c8ff}} .tier{{background:#171e28;color:#b6c1d0;border-color:var(--line)}}
.detail-btn{{background:#0e141b;color:var(--muted);border:1px solid var(--line);border-radius:8px;padding:7px;cursor:pointer}}
.quick-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;padding:0 14px 12px}} .quick-grid>div,.watch-row>div,.detail-columns section{{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px}}
.quick-grid span,.watch-row label{{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}} .quick-grid b{{font-size:15px}} .quick-grid em{{display:block;color:var(--muted);font-size:10px;font-style:normal;margin-top:3px}} .resonance{{color:var(--gold);letter-spacing:1px}}
.watch-row{{padding:0 14px 12px}} .tag{{display:inline-block;padding:4px 7px;border-radius:6px;background:#202936;color:#b5c1cf;font-size:10px;margin:2px}} .watch-tag{{background:#23344a;color:#b5d1ff}} .muted-tag{{background:#1b222b;color:var(--muted)}}
.stock-detail{{display:none;padding:0 14px 14px}} .stock-card.open .stock-detail{{display:block}} .detail-columns{{display:grid;grid-template-columns:1.2fr 1fr;gap:10px}} h4{{margin:0 0 10px;font-size:13px}}
.factor-row{{margin-bottom:9px}} .factor-head{{display:flex;justify-content:space-between;font-size:11px}} .factor-detail,.evidence{{color:var(--muted);font-size:11px;line-height:1.5}} .evidence div{{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}} .evidence b{{min-width:90px;color:#c8d1dc}}
.footer{{padding:16px;text-align:center;color:#596574;font-size:11px}}
@media(max-width:1000px){{.decision,.market,.layout2{{grid-template-columns:1fr 1fr}} .stock-main{{grid-template-columns:32px 1fr 100px}} .badges,.detail-btn{{grid-column:auto}} .quick-grid{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:680px){{.container{{padding:12px}} .header{{display:block}} .meta{{text-align:left;margin-top:8px}} .decision,.market,.layout2,.detail-columns{{grid-template-columns:1fr}} .metrics{{grid-template-columns:repeat(3,1fr)}} .stock-main{{grid-template-columns:28px 1fr 85px}} .score,.badges,.detail-btn{{grid-column:2}} .quick-grid{{grid-template-columns:repeat(2,1fr)}} .filters input{{min-width:0;width:100%}} .count{{margin-left:0}}}}
</style>
</head>
<body>
<div class="container">
  <header class="header">
    <div>
      <h1>七因子股票决策仪表盘</h1>
      <div class="sub">{esc(data.get('model', '连板潜力七因子模型'))}</div>
    </div>
    <div class="meta">
      <div>扫描日期：{esc(data.get('scan_date'))}</div>
      <div>扫描时间：{esc(data.get('scan_time'))}</div>
      <div>系统版本：{esc(data.get('system_version'))}</div>
    </div>
  </header>

  <section class="section">
    <div class="section-title">今日决策卡</div>
    <div class="decision">
      <div class="decision-item"><label>市场状态</label><strong>{esc(state)} · 情绪 {esc(sent.get('sentiment_label', '-'))}</strong></div>
      <div class="decision-item"><label>操作倾向</label><strong>{esc(action)}</strong></div>
      <div class="decision-item"><label>核心关注</label><strong>{esc(focus_text)}</strong></div>
      <div class="decision-item"><label>主要风险</label><strong>{esc(risk)}</strong></div>
      <div class="decision-item"><label>明日验证</label><strong>{esc(validate)}</strong></div>
    </div>
  </section>

  <section class="section market">
    <div class="market-main">
      <div class="state"><div class="dot"></div><div><div class="sub">市场情绪</div><div class="state-score">{esc(sent.get('sentiment_score', '-'))}</div></div></div>
      <div class="metrics">
        <div class="metric"><span>涨停</span><b class="up">{esc(sent.get('limit_up_count'))}</b></div>
        <div class="metric"><span>跌停</span><b class="down">{esc(sent.get('limit_down_count'))}</b></div>
        <div class="metric"><span>强势股</span><b>{esc(sent.get('strong_count'))}</b></div>
        <div class="metric"><span>炸板率</span><b>{esc(sent.get('explosion_rate'))}%</b></div>
        <div class="metric"><span>最高连板</span><b>{esc(sent.get('max_boards_est'))}</b></div>
        <div class="metric"><span>候选数</span><b>{esc(len(candidates))}</b></div>
      </div>
    </div>
    <div class="market-main">
      <div class="sub">今日关注主线</div>
      <div class="concepts" style="margin-top:10px">{concept_tags or '<span class="muted">暂无概念数据</span>'}</div>
    </div>
  </section>

  <section class="section layout2">
    <div>
      <div class="section-title">板块强度 TOP10</div>
      <table class="table">
        <thead><tr><th>#</th><th>板块</th><th>均涨幅</th><th>涨停</th><th>强势</th></tr></thead>
        <tbody>{sector_rows}</tbody>
      </table>
    </div>
    <div>
      <div class="section-title">模型配置</div>
      <div class="sub">池分布</div>
      <div class="concepts" style="margin-top:8px">{pool_html}</div>
      <div class="sub" style="margin-top:14px">七因子权重</div>
      <div class="concepts" style="margin-top:8px">{weight_html}</div>
    </div>
  </section>

  <section class="section">
    <div class="section-title">候选池</div>
    <div class="filters">
      <input id="search" placeholder="搜索股票 / 代码 / 板块">
      <select id="sort">
        <option value="default">推荐排序</option>
        <option value="score">调整分从高到低</option>
        <option value="change">今日涨幅</option>
        <option value="prob">连板概率</option>
      </select>
      <button class="filter-btn active" data-pool="全部">全部</button>
      <button class="filter-btn" data-pool="重点观察">重点观察</button>
      <button class="filter-btn" data-pool="预备池">预备池</button>
      <button class="filter-btn" data-pool="观察池">观察池</button>
      <button class="filter-btn" data-grade="A">A级</button>
      <button class="filter-btn" data-grade="B">B级</button>
      <span id="count" class="count"></span>
    </div>
    <div id="stocks" class="stock-list" style="margin-top:12px">{cards}</div>
  </section>

  <div class="footer">连板潜力七因子选股系统 · 页面仅重新组织展示，不改变选股评分逻辑 · 数据仅供研究参考，不构成投资建议</div>
</div>

<script>
function toggleDetail(btn) {{
  const card = btn.closest('.stock-card');
  const open = card.classList.toggle('open');
  btn.textContent = open ? '收起' : '展开';
}}
const buttons = document.querySelectorAll('.filter-btn');
const search = document.getElementById('search');
const sort = document.getElementById('sort');
const container = document.getElementById('stocks');
const count = document.getElementById('count');
let pool = '全部';
let grade = '';

buttons.forEach(btn => btn.addEventListener('click', () => {{
  if (btn.dataset.pool !== undefined) {{
    pool = btn.dataset.pool;
    buttons.forEach(b => {{ if (b.dataset.pool !== undefined) b.classList.remove('active'); }});
    btn.classList.add('active');
  }}
  if (btn.dataset.grade !== undefined) {{
    grade = btn.dataset.grade;
    buttons.forEach(b => {{ if (b.dataset.grade !== undefined) b.classList.remove('active'); }});
    btn.classList.add('active');
  }}
  apply();
}}));
search.addEventListener('input', apply);
sort.addEventListener('change', apply);

function apply() {{
  let cards = [...container.children];
  const q = search.value.trim().toLowerCase();
  cards.forEach(card => {{
    const okPool = pool === '全部' || card.dataset.pool === pool;
    const okGrade = !grade || card.dataset.grade === grade;
    const okSearch = !q || card.dataset.name.toLowerCase().includes(q);
    card.style.display = okPool && okGrade && okSearch ? '' : 'none';
  }});
  cards.sort((a, b) => {{
    const sa = parseFloat(a.querySelector('.score b')?.textContent || 0);
    const sb = parseFloat(b.querySelector('.score b')?.textContent || 0);
    const ca = parseFloat(a.querySelector('.price span')?.textContent || 0);
    const cb = parseFloat(b.querySelector('.price span')?.textContent || 0);
    const pa = parseFloat(a.querySelector('.quick-grid div:nth-child(2) b')?.textContent || 0);
    const pb = parseFloat(b.querySelector('.quick-grid div:nth-child(2) b')?.textContent || 0);
    if (sort.value === 'score') return sb - sa;
    if (sort.value === 'change') return cb - ca;
    if (sort.value === 'prob') return pb - pa;
    return parseInt(a.dataset.tier || 99) - parseInt(b.dataset.tier || 99);
  }});
  cards.forEach(card => container.appendChild(card));
  count.textContent = `显示 ${{cards.filter(card => card.style.display !== 'none').length}} / ${{cards.length}}`;
}}
apply();
</script>
</body>
</html>"""


def write_page(html_text):
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_text)


def run():
    print("\n[Pages] 开始生成网页...")
    data = load_data()
    html_text = generate_html(data)
    write_page(html_text)
    print(f"[Pages] 网页已生成：{OUTPUT_HTML}（{len(html_text)} 字节）")
    return {"output": OUTPUT_HTML, "size": len(html_text)}


if __name__ == "__main__":
    run()
