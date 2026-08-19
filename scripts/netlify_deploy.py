#!/usr/bin/env python3
"""
Netlify 自动部署模块 — 连板潜力七因子选股系统
读取 seven_factor_latest.json → 生成自包含 HTML → 部署到 Netlify
被 seven_factor_scanner.py 主流程末尾调用，也可独立运行。

环境变量（必须）：
  NETLIFY_AUTH_TOKEN  — Netlify Personal Access Token
  NETLIFY_SITE_ID     — Netlify 站点 ID
"""

import json
import os
import zipfile
import io
import urllib.request
import ssl
import time
from datetime import datetime

# === 路径 ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LATEST_JSON = os.path.join(DATA_DIR, "seven_factor_latest.json")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def load_config():
    """从环境变量读取 Netlify 配置（不再依赖本地 config 文件）"""
    token = os.environ.get("NETLIFY_AUTH_TOKEN", "")
    site_id = os.environ.get("NETLIFY_SITE_ID", "")
    if not token:
        raise ValueError("环境变量 NETLIFY_AUTH_TOKEN 未设置")
    if not site_id:
        raise ValueError("环境变量 NETLIFY_SITE_ID 未设置")
    return {
        "site_id": site_id,
        "auth_token": token,
        "api_base": "https://api.netlify.com/api/v1",
        "url": "https://seven-factor-stock-picker.netlify.app",
    }


def load_data():
    with open(LATEST_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# HTML 生成
# ============================================================

def _fmt_pct(v, sign=True):
    if v is None:
        return "-"
    prefix = "+" if sign and v > 0 else ""
    return f"{prefix}{v:.1f}%"


def _pool_badge(pool):
    colors = {
        "重点观察": "#e74c3c",
        "预备池": "#e67e22",
        "观察池": "#3498db",
        "淘汰": "#95a5a6",
    }
    c = colors.get(pool, "#95a5a6")
    return f'<span class="badge" style="background:{c}">{pool}</span>'


def _tier_badge(tier_label, tag):
    tier_colors = {
        "P1": "#27ae60",
        "P2": "#2980b9",
        "P3": "#f39c12",
        "P4": "#e67e22",
        "P5": "#e74c3c",
    }
    c = tier_colors.get(tier_label, "#7f8c8d")
    return f'<span class="tier-badge" style="border-color:{c};color:{c}">{tier_label} {tag}</span>'


def _resonance_dots(count):
    filled = "●" * count
    empty = "○" * (3 - count)
    return f'<span class="resonance">{filled}{empty}</span> {count}/3'


def generate_html(data):
    scan_date = data.get("scan_date", "")
    scan_time = data.get("scan_time", "")
    version = data.get("system_version", "")
    model = data.get("model", "")
    sent = data.get("market_sentiment", {})
    sectors = data.get("sector_rankings", [])
    candidates = data.get("candidates", [])
    weights = data.get("weight_config", {})
    threshold = data.get("threshold", {})

    # 按池分组并按 adjusted_total 排序
    pool_order = {"重点观察": 0, "预备池": 1, "观察池": 2, "淘汰": 3}
    candidates_sorted = sorted(candidates, key=lambda r: (pool_order.get(r.get("pool", ""), 9), -r.get("adjusted_total", 0)))

    # === 情绪卡片 ===
    sent_html = f"""
    <div class="sentiment-card">
      <div class="sent-item"><span class="sent-label">涨停</span><span class="sent-val up">{sent.get('limit_up_count','-')}</span></div>
      <div class="sent-item"><span class="sent-label">跌停</span><span class="sent-val down">{sent.get('limit_down_count','-')}</span></div>
      <div class="sent-item"><span class="sent-label">强势股</span><span class="sent-val">{sent.get('strong_count','-')}</span></div>
      <div class="sent-item"><span class="sent-label">炸板率</span><span class="sent-val">{sent.get('explosion_rate','-')}%</span></div>
      <div class="sent-item"><span class="sent-label">最高连板</span><span class="sent-val">{sent.get('max_boards_est','-')}</span></div>
      <div class="sent-item"><span class="sent-label">情绪分</span><span class="sent-val {'up' if sent.get('sentiment_score',0)>=60 else 'down'}">{sent.get('sentiment_score','-')}</span></div>
      <div class="sent-item"><span class="sent-label">情绪</span><span class="sent-val">{sent.get('sentiment_label','-')}</span></div>
    </div>"""

    # === 板块排行 top10 ===
    sector_rows = ""
    for s in sectors[:10]:
        sector_rows += f"""
      <tr>
        <td>{s['rank']}</td>
        <td class="sector-name">{s['name']}</td>
        <td class="{'up' if s['avg_change']>=0 else 'down'}">{_fmt_pct(s['avg_change'])}</td>
        <td>{s.get('limit_up_count','-')}</td>
        <td>{s.get('strong_count','-')}</td>
      </tr>"""

    # === 候选股表格 ===
    table_rows = ""
    for r in candidates_sorted:
        sc = r.get("scores", {})
        ks = r.get("kline_signals", {})
        hist = r.get("history", {})
        res = r.get("resonance", {})
        rec = r.get("recency", {})
        watch_tags = "".join(f'<span class="watch-tag">{t}</span>' for t in r.get("next_day_watch", []))

        score_bar_color = "#e74c3c" if r.get("adjusted_total", 0) >= 65 else "#e67e22" if r.get("adjusted_total", 0) >= 60 else "#3498db" if r.get("adjusted_total", 0) >= 50 else "#95a5a6"
        score_bar_width = min(r.get("adjusted_total", 0), 100)

        table_rows += f"""
      <tr>
        <td class="code">{r['code']}</td>
        <td class="name">{r['name']}</td>
        <td>{r.get('sector','-')}</td>
        <td>{r.get('price','-')}</td>
        <td class="{'up' if r.get('change_pct',0)>=0 else 'down'}">{_fmt_pct(r.get('change_pct',0))}</td>
        <td>{r.get('turnover_rate','-')}%</td>
        <td>{r.get('circ_mcap_yi','-')}</td>
        <td class="score-cell">
          <span class="score-val">{r.get('adjusted_total','-')}</span>
          <div class="score-bar-bg"><div class="score-bar" style="width:{score_bar_width}%;background:{score_bar_color}"></div></div>
          <span class="score-orig">原{sc.get('total','-')}</span>
        </td>
        <td>{_tier_badge(rec.get('tier_label',''), rec.get('tag',''))}</td>
        <td>{_pool_badge(r.get('pool','-'))}</td>
        <td class="grade-{r.get('grade','').lower()}">{r.get('grade','-')}</td>
        <td>{_resonance_dots(res.get('count',0))}</td>
        <td>{r.get('lianban_probability','-')}%</td>
        <td>{hist.get('limit_up_count','-')}次/{hist.get('max_consecutive','-')}连</td>
        <td>{hist.get('days_since_last_lu','-')}日</td>
        <td class="watch-tags">{watch_tags}</td>
      </tr>"""

    # === 权重配置 ===
    weight_items = "".join(f"<span class='weight-chip'><b>{k}</b> {v}分</span>" for k, v in weights.items())
    threshold_items = "".join(f"<span class='threshold-chip'><b>{k}</b> {v}</span>" for k, v in threshold.items())

    # === 池统计 ===
    pool_counts = {}
    for r in candidates_sorted:
        p = r.get("pool", "未知")
        pool_counts[p] = pool_counts.get(p, 0) + 1
    pool_stats = "".join(f"<span class='pool-stat'><b>{p}</b> {c}只</span>" for p, c in pool_counts.items())

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>连板潜力七因子选股系统 {version}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:#0f1117; color:#e0e0e0; padding:12px; font-size:14px; }}
  .header {{ text-align:center; padding:20px 0; border-bottom:1px solid #2a2d35; margin-bottom:16px; }}
  .header h1 {{ font-size:22px; color:#fff; margin-bottom:6px; }}
  .header .sub {{ color:#888; font-size:13px; }}
  .header .meta {{ margin-top:8px; font-size:12px; color:#666; }}
  .header .meta span {{ margin:0 8px; }}
  .section {{ background:#1a1d27; border-radius:10px; padding:16px; margin-bottom:14px; border:1px solid #2a2d35; }}
  .section-title {{ font-size:16px; font-weight:700; color:#fff; margin-bottom:12px; padding-left:10px; border-left:3px solid #3498db; }}
  .sentiment-card {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }}
  .sent-item {{ display:flex; flex-direction:column; align-items:center; min-width:70px; padding:8px 6px; background:#22252f; border-radius:8px; }}
  .sent-label {{ font-size:11px; color:#888; margin-bottom:4px; }}
  .sent-val {{ font-size:18px; font-weight:700; color:#fff; }}
  .sent-val.up {{ color:#e74c3c; }}
  .sent-val.down {{ color:#2ecc71; }}
  .pool-stats {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }}
  .pool-stat {{ background:#22252f; padding:6px 14px; border-radius:20px; font-size:13px; }}
  .pool-stat b {{ color:#3498db; }}
  .config-row {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }}
  .weight-chip, .threshold-chip {{ background:#22252f; padding:4px 10px; border-radius:4px; font-size:12px; color:#aaa; }}
  .weight-chip b, .threshold-chip b {{ color:#e67e22; }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
  th {{ background:#22252f; color:#888; padding:8px 6px; text-align:center; white-space:nowrap; position:sticky; top:0; }}
  th:first-child, td:first-child {{ text-align:left; }}
  td {{ padding:6px; border-bottom:1px solid #22252f; text-align:center; white-space:nowrap; }}
  tr:hover {{ background:#1e2128; }}
  .code {{ font-family:monospace; color:#3498db; }}
  .name {{ font-weight:600; color:#fff; }}
  .sector-name {{ color:#bbb; }}
  .up {{ color:#e74c3c; }}
  .down {{ color:#2ecc71; }}
  .score-cell {{ text-align:left; min-width:120px; }}
  .score-val {{ font-weight:700; font-size:14px; color:#fff; }}
  .score-bar-bg {{ width:60px; height:5px; background:#333; border-radius:3px; display:inline-block; margin:0 6px; vertical-align:middle; }}
  .score-bar {{ height:100%; border-radius:3px; }}
  .score-orig {{ font-size:11px; color:#666; }}
  .badge {{ padding:2px 8px; border-radius:4px; font-size:11px; color:#fff; }}
  .tier-badge {{ padding:1px 6px; border-radius:3px; font-size:10px; border:1px solid; white-space:nowrap; }}
  .grade-a {{ color:#e74c3c; font-weight:700; }}
  .grade-b {{ color:#e67e22; font-weight:700; }}
  .grade-c {{ color:#3498db; font-weight:700; }}
  .grade-d {{ color:#888; }}
  .resonance {{ color:#f1c40f; letter-spacing:1px; }}
  .watch-tags {{ text-align:left; max-width:220px; white-space:normal; }}
  .watch-tag {{ display:inline-block; background:#2a2d35; padding:1px 6px; border-radius:3px; font-size:10px; margin:1px; color:#aaa; }}
  .table-wrap {{ overflow-x:auto; max-height:75vh; overflow-y:auto; }}
  .footer {{ text-align:center; padding:16px; color:#555; font-size:11px; }}
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  @media(max-width:768px) {{ .two-col {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
  <div class="header">
    <h1>连板潜力七因子选股系统 {version}</h1>
    <div class="sub">{model}</div>
    <div class="meta">
      <span>扫描日期：{scan_date}</span>
      <span>扫描时间：{scan_time}</span>
      <span>数据源：新浪财经API</span>
    </div>
  </div>

  <div class="section">
    <div class="section-title">市场情绪</div>
    {sent_html}
  </div>

  <div class="two-col">
    <div class="section">
      <div class="section-title">板块强度 TOP10</div>
      <table>
        <thead><tr><th>#</th><th>板块</th><th>均涨幅</th><th>涨停</th><th>强势</th></tr></thead>
        <tbody>{sector_rows}
        </tbody>
      </table>
    </div>
    <div class="section">
      <div class="section-title">模型配置</div>
      <div class="pool-stats">{pool_stats}</div>
      <div style="font-size:12px;color:#888;margin-bottom:6px;">七因子权重</div>
      <div class="config-row">{weight_items}</div>
      <div style="font-size:12px;color:#888;margin:10px 0 6px;">入池门槛</div>
      <div class="config-row">{threshold_items}</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">候选股总览（{len(candidates_sorted)}只，按池+调整分排序）</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>板块</th><th>现价</th><th>涨幅</th><th>换手率</th>
            <th>流通市值(亿)</th><th>调整分</th><th>优先级</th><th>池</th><th>评级</th>
            <th>共振</th><th>连板概率</th><th>涨停史</th><th>距上次涨停</th><th>观察标签</th>
          </tr>
        </thead>
        <tbody>{table_rows}
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    连板潜力七因子选股系统 {version} · 每工作日 15:35 自动更新 · 数据仅供研究参考，不构成投资建议
  </div>
</body>
</html>"""
    return html


# ============================================================
# Netlify 部署
# ============================================================

def deploy_to_netlify(html_content, config):
    """通过 Netlify API 部署单个 index.html（zip 方式）"""
    site_id = config["site_id"]
    token = config["auth_token"]
    api_base = config.get("api_base", "https://api.netlify.com/api/v1")

    # 构建 zip（含 index.html + _headers）
    # _headers 强制 Content-Type: text/html，避免 Netlify 把 index.html 当 text/plain 返回
    headers_content = "/*\n  Content-Type: text/html; charset=UTF-8\n"
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html_content)
        zf.writestr("_headers", headers_content)
    zip_bytes = zip_buffer.getvalue()

    url = f"{api_base}/sites/{site_id}/deploys"
    req = urllib.request.Request(
        url,
        data=zip_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/zip",
        },
        method="POST",
    )

    resp = urllib.request.urlopen(req, context=SSL_CTX, timeout=60)
    result = json.loads(resp.read().decode("utf-8"))
    return result


def run():
    """主入口：读数据 → 生成 HTML → 部署"""
    print("\n[Netlify] 开始同步部署...")
    config = load_config()
    data = load_data()

    html = generate_html(data)

    # 本地保存一份 HTML 用于调试
    html_path = os.path.join(DATA_DIR, "netlify_index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    result = deploy_to_netlify(html, config)
    deploy_url = result.get("ssl_url") or result.get("url") or config.get("url", "")
    deploy_id = result.get("id", "")
    state = result.get("state", "")

    # 轮询部署状态（最多 45 秒）
    if state in ("uploading", "processing", "uploaded", "queued"):
        token = config["auth_token"]
        api_base = config.get("api_base", "https://api.netlify.com/api/v1")
        for _ in range(10):
            time.sleep(3)
            try:
                sreq = urllib.request.Request(
                    f"{api_base}/deploys/{deploy_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    method="GET",
                )
                sresp = urllib.request.urlopen(sreq, context=SSL_CTX, timeout=15)
                sresult = json.loads(sresp.read().decode("utf-8"))
                state = sresult.get("state", state)
                if state in ("ready", "error"):
                    break
            except Exception:
                break

    if state == "ready":
        print(f"[Netlify] 部署成功！URL: {deploy_url}")
    else:
        print(f"[Netlify] 部署已提交，状态: {state} (URL: {deploy_url})")

    return {"state": state, "url": deploy_url, "deploy_id": deploy_id}


if __name__ == "__main__":
    run()
