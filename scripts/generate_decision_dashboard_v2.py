#!/usr/bin/env python3
"""Phase 2 decision dashboard generator.
Reads data/seven_factor_latest.json and writes docs/index.html.
Presentation-only: does not change scanner logic or scoring data.
"""
import html
import json
import os
from string import Template

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "seven_factor_latest.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "index.html")


def esc(v):
    return html.escape(str(v if v is not None else "-"))


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def pct(v):
    try:
        return f"{num(v):+.1f}%"
    except Exception:
        return esc(v)


def cls_pct(v):
    return "up" if num(v) >= 0 else "down"


def sentiment_class(score):
    s = num(score, 50)
    if s >= 70:
        return "hot"
    if s >= 55:
        return "warm"
    if s < 40:
        return "cold"
    return "normal"


def action_text(sentiment, focus_count, ready_count):
    score = num(sentiment.get("sentiment_score"), 50)
    label = str(sentiment.get("sentiment_label", "正常"))
    if score < 40:
        return "谨慎观察", "市场处于弱势环境，重点看防守与次日确认", "不要因为个股高分就强行出手"
    if score < 55:
        return "轻仓试错", "市场偏弱，优先等主线和资金进一步确认", "重点看预备池而非盲目追涨"
    if score < 70:
        return "结构性参与", f"当前情绪为{label}，适合围绕强板块挑核心", "优先看重点观察池"
    return "积极参与", f"当前情绪为{label}，市场具备较强进攻条件", "优先寻找主线龙头与首板前候选"


def pool_class(pool):
    return {
        "重点观察": "focus",
        "预备池": "ready",
        "观察池": "watch",
        "淘汰": "drop",
    }.get(pool, "drop")


def tier_class(tier):
    return {1: "p1", 2: "p2", 3: "p3", 4: "p4", 5: "p5"}.get(int(num(tier, 99)), "p5")


def signal_tags(value, limit=4):
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            if v in (None, False, "", 0):
                continue
            if isinstance(v, (dict, list, tuple)):
                items.append(f"{k}: {v}")
            else:
                items.append(f"{k}: {v}")
    elif isinstance(value, (list, tuple, set)):
        items = [str(x) for x in value]
    elif value in (None, ""):
        items = []
    else:
        items = [str(value)]
    if not items:
        return '<span class="muted">暂无</span>'
    return "".join(f'<span class="tag">{esc(x)}</span>' for x in items[:limit])


def factor_rows(r):
    scores = r.get("scores", {})
    spec = [
        ("个股辨识度", "stock_recognition", 25),
        ("资金预热", "capital_preheat", 20),
        ("K线筹码", "kline_chip", 15),
        ("题材催化", "theme_catalyst", 10),
        ("板块强度", "sector_strength", 10),
        ("市值流动性", "market_cap_liquidity", 15),
        ("情绪环境", "sentiment", 5),
    ]
    rows = []
    for name, key, maxv in spec:
        v = num(scores.get(key), 0)
        width = max(0, min(100, v / maxv * 100 if maxv else 0))
        rows.append(
            f'<div class="factor"><div class="factor-head"><span>{esc(name)}</span><b>{v:.1f}/{maxv}</b></div>'
            f'<div class="bar"><i style="width:{width:.0f}%"></i></div></div>'
        )
    return "".join(rows)


def focus_card(r, rank):
    rec = r.get("recency") or {}
    hist = r.get("history") or {}
    res = r.get("resonance") or {}
    score = num(r.get("adjusted_total"))
    change = num(r.get("change_pct"))
    tier = int(num(rec.get("tier"), 99))
    dots = "●" * int(num(res.get("count"), 0)) + "○" * max(0, 3 - int(num(res.get("count"), 0)))
    return f'''<article class="focus-card">
      <div class="focus-rank">TOP {rank}</div>
      <div class="focus-main">
        <div><div class="stock-title">{esc(r.get("name"))} <small>{esc(r.get("code"))}</small></div>
        <div class="stock-sub">{esc(r.get("sector", "未分类"))} · {esc(r.get("sw_industry", "未分类"))}</div></div>
        <div class="quote"><strong>{esc(r.get("price"))}</strong><span class="{cls_pct(change)}">{pct(change)}</span></div>
        <div class="score"><strong>{score:.1f}</strong><small>调整分</small></div>
        <span class="pill {pool_class(r.get("pool"))}">{esc(r.get("pool"))}</span>
        <span class="pill {tier_class(tier)}">P{tier} {esc(rec.get("tag", ""))}</span>
      </div>
      <div class="focus-metrics">
        <div><span>三共振</span><b class="resonance">{dots}</b><em>{int(num(res.get("count"),0))}/3</em></div>
        <div><span>连板概率</span><b>{esc(r.get("lianban_probability"))}%</b></div>
        <div><span>换手率</span><b>{esc(r.get("turnover_rate"))}%</b></div>
        <div><span>流通市值</span><b>{esc(r.get("circ_mcap_yi"))}亿</b></div>
        <div><span>历史涨停</span><b>{esc(hist.get("limit_up_count"))}次</b></div>
        <div><span>距上次涨停</span><b>{esc(hist.get("days_since_last_lu"))}日</b></div>
      </div>
      <div class="reason"><b>为什么排在前面</b><span>{esc((r.get("next_day_watch") or ["等待信号确认"])[0])}</span><span>{esc((r.get("next_day_watch") or ["-", "-"])[1] if len(r.get("next_day_watch") or []) > 1 else "-")}</span></div>
      <details><summary>查看七因子证据</summary><div class="factor-grid">{factor_rows(r)}</div>
        <div class="signal-block"><div><label>明日关注</label>{signal_tags(r.get("next_day_watch"), 8)}</div><div><label>资金</label>{signal_tags(r.get("capital_signals"), 6)}</div><div><label>K线</label>{signal_tags(r.get("kline_signals"), 6)}</div></div>
      </details>
    </article>'''


def pool_row(r, rank):
    rec = r.get("recency") or {}
    score = num(r.get("adjusted_total"))
    return f'''<div class="pool-row"><span class="rank">{rank}</span><div class="stock-id"><b>{esc(r.get("name"))}</b><small>{esc(r.get("code"))} · {esc(r.get("sector", "-"))}</small></div><span class="pill {pool_class(r.get("pool"))}">{esc(r.get("pool"))}</span><span class="pill {tier_class(rec.get("tier", 99))}">P{esc(rec.get("tier", "-"))}</span><strong class="score-num">{score:.1f}</strong><span class="{cls_pct(r.get("change_pct"))}">{pct(r.get("change_pct"))}</span></div>'''


def render(data):
    sent = data.get("market_sentiment") or {}
    summary = data.get("summary") or {}
    candidates = list(data.get("candidates") or [])
    candidates.sort(key=lambda r: (int(num((r.get("recency") or {}).get("tier"), 99)), -num(r.get("adjusted_total"))))
    focus = [r for r in candidates if r.get("pool") == "重点观察"][:8]
    ready = [r for r in candidates if r.get("pool") == "预备池"][:15]
    watch = [r for r in candidates if r.get("pool") == "观察池"][:15]
    sectors = sorted(data.get("sector_rankings") or [], key=lambda x: num(x.get("avg_change")), reverse=True)[:6]
    concepts = sorted(data.get("concept_rankings") or [], key=lambda x: num(x.get("avg_change")), reverse=True)[:10]
    action, desc, caution = action_text(sent, len(focus), len(ready))
    score = num(sent.get("sentiment_score"), 0)
    sentiment_label = sent.get("sentiment_label", "正常")

    pool_html = "".join(pool_row(r, i + 1) for i, r in enumerate(ready + watch))
    focus_html = "".join(focus_card(r, i + 1) for i, r in enumerate(focus))
    sector_html = "".join(
        f'<div class="sector-item"><span>#{esc(s.get("rank"))}</span><b>{esc(s.get("name"))}</b><strong class="{cls_pct(s.get("avg_change"))}">{pct(s.get("avg_change"))}</strong><small>{esc(s.get("limit_up_count"))}涨停 · {esc(s.get("strong_count"))}强势</small></div>'
        for s in sectors
    )
    concept_html = "".join(
        f'<span class="concept"><b>#{esc(c.get("rank"))}</b>{esc(c.get("name"))}<em class="{cls_pct(c.get("avg_change"))}">{pct(c.get("avg_change"))}</em></span>'
        for c in concepts
    )

    template = Template(r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七因子 · 第二阶段决策仪表盘</title>
<style>
:root{--bg:#0a0d12;--panel:#121720;--panel2:#171d27;--line:#26303d;--text:#e8eef7;--muted:#8792a4;--blue:#6ea8ff;--up:#ff6575;--down:#3bd39a;--gold:#f5c85b;--orange:#ffad5c;--redbg:#351c23;--bluebg:#182941;--orangebg:#362619}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px}.wrap{max-width:1480px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:16px}.brand h1{font-size:26px;margin:0}.brand p{margin:6px 0 0;color:var(--muted);font-size:12px}.meta{text-align:right;color:var(--muted);font-size:11px;line-height:1.8}.hero{display:grid;grid-template-columns:1.15fr 1fr;gap:14px;margin-bottom:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:15px}.decision{padding:20px}.decision-head{display:flex;justify-content:space-between;align-items:center}.decision-kicker{font-size:11px;color:var(--muted)}.decision-title{font-size:28px;font-weight:900;margin-top:4px}.decision-desc{color:var(--muted);margin:8px 0 16px;line-height:1.55}.decision-caution{font-size:12px;color:#d2d9e5;padding:10px 12px;background:#10151d;border:1px solid #212b38;border-radius:9px}.sent-score{font-size:40px;font-weight:900}.state-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:7px}.state-dot.hot{background:var(--up)}.state-dot.warm{background:var(--orange)}.state-dot.normal{background:var(--blue)}.state-dot.cold{background:var(--down)}.mini-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:16px}.mini{background:#10151d;border:1px solid #212b38;border-radius:9px;padding:10px}.mini span{display:block;color:var(--muted);font-size:10px}.mini b{display:block;font-size:17px;margin-top:4px}.action-box{padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:10px}.action{padding:14px;background:#10151d;border:1px solid #212b38;border-radius:10px}.action strong{display:block;font-size:25px;margin-top:4px}.action small{color:var(--muted)}.action.focus{border-color:#63303a}.action.ready{border-color:#654527}.section{margin:14px 0}.section-head{display:flex;justify-content:space-between;align-items:end;padding:16px 16px 10px}.section-head h2{font-size:17px;margin:0}.section-head p{font-size:11px;color:var(--muted);margin:5px 0 0}.focus-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 16px 16px}.focus-card{background:var(--panel2);border:1px solid var(--line);border-radius:13px;padding:15px}.focus-rank{color:var(--gold);font-size:10px;font-weight:800}.focus-main{display:grid;grid-template-columns:1.6fr 100px 90px auto auto;gap:10px;align-items:center;margin-top:7px}.stock-title{font-size:16px;font-weight:900}.stock-title small{font-size:10px;color:var(--muted)}.stock-sub{font-size:10px;color:var(--muted);margin-top:4px}.quote strong{display:block;font-size:17px}.score strong{font-size:22px}.score small{display:block;color:var(--muted);font-size:9px}.pill{display:inline-flex;align-items:center;padding:5px 8px;border-radius:7px;font-size:10px;border:1px solid transparent;white-space:nowrap}.focus{background:var(--redbg);color:#ff9ca7}.ready{background:var(--orangebg);color:#ffc27e}.watch{background:var(--bluebg);color:#b7d0ff}.drop{background:#202731;color:var(--muted)}.p1{background:#302b18;color:var(--gold)}.p2{background:#1e2938;color:#b9ceef}.p3,.p4,.p5{background:#252931;color:#aab3c0}.up{color:var(--up)}.down{color:var(--down)}.focus-metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:7px;margin:13px 0}.focus-metrics>div{background:#10151d;border:1px solid #212b38;border-radius:8px;padding:8px}.focus-metrics span{display:block;color:var(--muted);font-size:9px}.focus-metrics b{display:block;font-size:13px;margin-top:4px}.focus-metrics em{font-style:normal;color:var(--muted);font-size:9px;margin-left:4px}.resonance{color:var(--gold)}.reason{display:flex;gap:8px;align-items:center;font-size:10px;color:var(--muted);padding:8px 10px;background:#0e131a;border-radius:8px}.reason b{color:#d9e0ea}.reason span{padding-left:8px;border-left:1px solid #303a47}.focus-card details{margin-top:9px}.focus-card summary{cursor:pointer;color:#aec6e9;font-size:10px}.factor-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:10px}.factor{background:#0e131a;border:1px solid #202a36;border-radius:8px;padding:7px}.factor-head{display:flex;justify-content:space-between;font-size:9px}.bar{height:4px;background:#293340;border-radius:5px;margin-top:5px;overflow:hidden}.bar i{display:block;height:100%;background:var(--blue)}.signal-block{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:9px}.signal-block>div{background:#0e131a;border:1px solid #202a36;border-radius:8px;padding:8px}.signal-block label{display:block;color:var(--muted);font-size:9px;margin-bottom:5px}.tag{display:inline-block;padding:3px 5px;margin:2px;background:#1c2430;border:1px solid #2a3544;border-radius:5px;font-size:9px;color:#cad5e5}.decision-layout{display:grid;grid-template-columns:1.05fr .95fr;gap:14px;padding:0 16px 16px}.sector-list{display:flex;flex-direction:column;gap:7px}.sector-item{display:grid;grid-template-columns:35px 1fr 70px 120px;gap:8px;align-items:center;background:#10151d;border:1px solid #212b38;border-radius:8px;padding:9px}.sector-item span,.sector-item small{color:var(--muted);font-size:9px}.sector-item b{font-size:12px}.sector-item strong{text-align:right}.concepts{display:flex;flex-wrap:wrap;gap:7px}.concept{background:#10151d;border:1px solid #212b38;border-radius:8px;padding:8px 9px;font-size:10px}.concept b{color:var(--gold);margin-right:4px}.concept em{font-style:normal;margin-left:7px}.pool-list{padding:0 16px 16px}.pool-row{display:grid;grid-template-columns:35px 1.8fr 90px 48px 70px 70px;align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid #202832}.pool-row:first-child{border-top:1px solid #202832}.rank{color:var(--muted);font-size:10px}.stock-id b{display:block;font-size:12px}.stock-id small{color:var(--muted);font-size:9px}.score-num{font-size:14px}.footer{text-align:center;color:#5f6b7d;font-size:10px;padding:18px}
@media(max-width:1050px){.hero,.decision-layout{grid-template-columns:1fr}.focus-grid{grid-template-columns:1fr}.focus-main{grid-template-columns:1fr 90px 80px auto}.focus-metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.wrap{padding:12px}.top{align-items:start;flex-direction:column}.meta{text-align:left}.mini-grid{grid-template-columns:repeat(2,1fr)}.action-box{grid-template-columns:1fr 1fr}.focus-main{grid-template-columns:1fr 80px}.focus-main .pill{margin-top:4px}.focus-metrics{grid-template-columns:repeat(2,1fr)}.reason{align-items:flex-start;flex-direction:column}.reason span{border-left:0;padding-left:0}.signal-block{grid-template-columns:1fr}.sector-item{grid-template-columns:28px 1fr 65px}.sector-item small{display:none}.pool-row{grid-template-columns:24px 1fr 70px 40px 56px}.pool-row>span:last-child{display:none}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><h1>七因子 · 决策仪表盘</h1><p>第二阶段：从“看数据”升级为“做决策” · 算法与候选池保持不变</p></div><div class="meta">扫描：$DATE $TIME<br>模型：$MODEL</div></div>
<section class="hero"><div class="card decision"><div class="decision-head"><div><div class="decision-kicker">当前市场状态</div><div class="decision-title"><span class="state-dot $MOOD"></span>$ACTION</div></div><div style="text-align:right"><div class="sent-score">$SCORE</div><div class="decision-kicker">情绪分 · $LABEL</div></div></div><div class="decision-desc">$DESC</div><div class="decision-caution">观察纪律：$CAUTION</div><div class="mini-grid"><div class="mini"><span>涨停</span><b class="up">$LUP</b></div><div class="mini"><span>跌停</span><b class="down">$LDN</b></div><div class="mini"><span>最高连板</span><b>$MAXBOARD</b></div><div class="mini"><span>炸板率</span><b>$EXPLODE%</b></div></div></div><div class="card action-box"><div class="action focus"><small>重点观察</small><strong>$FOCUS_COUNT 只</strong><small>≥65分 + 三共振</small></div><div class="action ready"><small>预备池</small><strong>$READY_COUNT 只</strong><small>等待确认</small></div><div class="action"><small>观察池</small><strong>$WATCH_COUNT 只</strong><small>只观察，不追</small></div><div class="action"><small>候选总数</small><strong>$TOTAL</strong><small>全候选池</small></div></div></section>
<section class="card section"><div class="section-head"><div><h2>① 今日最值得盯的股票</h2><p>只看重点观察池；先看优先级，再看调整分</p></div></div><div class="focus-grid">$FOCUS_HTML</div></section>
<section class="card section"><div class="section-head"><div><h2>② 主线与板块</h2><p>先确认市场共识，再决定候选股是否值得继续看</p></div></div><div class="decision-layout"><div><div class="section-head" style="padding:0 0 8px"><div><h2 style="font-size:13px">行业强度 TOP6</h2></div></div><div class="sector-list">$SECTOR_HTML</div></div><div><div class="section-head" style="padding:0 0 8px"><div><h2 style="font-size:13px">概念强度 TOP10</h2></div></div><div class="concepts">$CONCEPT_HTML</div></div></div></section>
<section class="card section"><div class="section-head"><div><h2>③ 预备池 / 观察池</h2><p>不抢跑，等板块、资金或价格结构出现确认</p></div><div class="decision-kicker">共 $SECONDARY_COUNT 只</div></div><div class="pool-list">$POOL_HTML</div></section>
<div class="footer">七因子第二阶段决策仪表盘 · 数据源与模型逻辑保持原系统不变 · 仅供研究参考，不构成投资建议</div>
</div></body></html>''')

    return template.substitute(
        DATE=esc(data.get("scan_date", "")), TIME=esc(data.get("scan_time", "")), MODEL=esc(data.get("model", "")),
        MOOD=sentiment_class(score), ACTION=esc(action), SCORE=f"{score:.1f}", LABEL=esc(sentiment_label),
        DESC=esc(desc), CAUTION=esc(caution), LUP=esc(sent.get("limit_up_count")), LDN=esc(sent.get("limit_down_count")),
        MAXBOARD=esc(sent.get("max_boards_est")), EXPLODE=esc(sent.get("explosion_rate")), TOTAL=esc(summary.get("total_scanned", len(candidates))),
        FOCUS_COUNT=esc(len(focus)), READY_COUNT=esc(len(ready)), WATCH_COUNT=esc(len(watch)), FOCUS_HTML=focus_html or '<div class="decision-caution">当前没有满足重点观察条件的股票。</div>',
        SECTOR_HTML=sector_html or '<div class="decision-caution">暂无行业数据。</div>', CONCEPT_HTML=concept_html or '<div class="decision-caution">暂无概念数据。</div>',
        POOL_HTML=pool_html or '<div class="decision-caution">当前无预备池/观察池数据。</div>', SECONDARY_COUNT=esc(len(ready)+len(watch)),
    )


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("latest candidate pool is empty; refuse to overwrite dashboard")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    page = render(data)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[Dashboard V2] generated {OUT_PATH}: {len(page)} bytes; candidates={len(candidates)}")


if __name__ == "__main__":
    main()
