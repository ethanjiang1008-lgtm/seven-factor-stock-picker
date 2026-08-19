#!/usr/bin/env python3
"""
连板潜力七因子选股系统 v1.2
Seven-Factor Consecutive Limit-Up Potential Scanner

v1.2 变更（修复首板前候选被已涨停股淹没的问题）：
- analyze_history 新增近期涨停追踪：距上次涨停天数、近3/5/10日涨停次数、当前连板数
- 新增 compute_recency_status：首板前候选(有涨停基因但近期无涨停)加5分优先；
  近3日有涨停降18分、近5日降10分、近10日降5分
- 排序改为先按优先级层级(P1首板前>P2无涨停史>P3近10日>P4近5日>P5近3日)，再按调整后分数
- 分级与入池基于调整后分数

v1.1 变更（基于 2025-08~2026-08 回测验证，1940 个 2 连板事件）：
- 权重从"题材/板块主导"调整为"股性+趋势+量能主导"
- K线因子重写：删除横盘蓄势（反向指标），改奖励趋势/均线多头
- 个股辨识度：显式纳入 120 日涨停次数 + 历史连板高度（≥60%权重）
- 市值流动性：取消小市值偏好，只奖励换手率健康区间
- 情绪环境：降为开关/系数，仅极端冰点时整体降权
- 门槛下调：重点观察 65 分 + 历史股性/趋势/量能三共振硬过滤

七因子模型 v1.2（满分100分 + 近期涨停调整）：
1. 个股辨识度 25分  2. 资金预热 20分  3. K线/筹码 15分
4. 题材催化 10分    5. 板块强度 10分  6. 市值/流动性 15分  7. 情绪环境 5分(系数)
+ 近期涨停调整：首板前候选 +5 / 近10日 -5 / 近5日 -10 / 近3日 -18
"""

import json
import sys
import time
import urllib.request
import ssl
import os
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 项目根目录（scripts/ 的上级目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 申万一级行业板块（31个）
SW_SECTORS = [
    ("sw_dz", "电子"), ("sw_tx", "通信"), ("sw_jsj", "计算机"),
    ("sw_jxsb", "机械设备"), ("sw_dlsb", "电力设备"), ("sw_qc", "汽车"),
    ("sw_ysjs", "有色金属"), ("sw_sysh", "石油石化"), ("sw_spyl", "食品饮料"),
    ("sw_yysw", "医药生物"), ("sw_jydq", "家用电器"), ("sw_nlmy", "农林牧渔"),
    ("sw_yx", "银行"), ("sw_fyjr", "非银金融"), ("sw_gfjg", "国防军工"),
    ("sw_jtys", "交通运输"), ("sw_jchg", "基础化工"), ("sw_gt", "钢铁"),
    ("sw_jzcl", "建筑材料"), ("sw_jzzs", "建筑装饰"), ("sw_qgzz", "轻工制造"),
    ("sw_fzfs", "纺织服饰"), ("sw_smls", "商贸零售"), ("sw_shfw", "社会服务"),
    ("sw_gysy", "公用事业"), ("sw_hb", "环保"), ("sw_mrhl", "美容护理"),
    ("sw_cm", "传媒"), ("sw_zh", "综合"), ("sw_fdc", "房地产"),
    ("sw_mt", "煤炭"),
]

# 非主题概念板块过滤名单（这些是市场结构/交易机制/业绩类标签，非投资主题）
NON_THEMATIC_CONCEPTS = {
    # 市值分类
    "小盘", "中盘", "大盘", "超大盘", "百元股", "低价股", "高价股", "低价",
    # 交易机制
    "融资融券", "沪深港通", "沪股通", "深股通", "含H股", "含B股", "含可转债", "含GDR", "GDR概念",
    # ST/特殊状态
    "ST板块", "*ST板块", "准ST股", "摘帽概念", "破净股", "破发股",
    # IPO/新股
    "次新股", "新股", "三板精选", "新三板",
    # 涨跌停/连板（日级别标签，非主题）
    "昨日涨停", "昨日连板", "昨日首板", "今日涨停", "昨日涨停股",
    # 业绩/财务
    "业绩预升", "业绩预降", "业绩亏损", "业绩扭亏",
    # 送转/分红
    "送转潜力", "高送转", "送转填权",
    # 机构重仓（被动分类）
    "基金重仓", "社保重仓", "保险重仓", "信托重仓", "券商重仓", "QFII重仓", "QFII持股",
    # 重组/资本运作
    "重组概念", "整体上市", "分拆上市", "资产注入",
    # 股权
    "股权激励", "员工持股",
    # 央企/国企
    "央企50",
    # 增持回购
    "增持回购", "回购",
    # 年度/月度标签
    "年度强势", "本月解禁",
    # 中字头
    "中字头",
    # 融资/租赁（非投资主题）
    "融资租赁", "房屋租赁",
    # 参股金融
    "参股金融", "金融参股",
    # 精选指数
    "精选指数",
}

CONCEPT_CACHE_PATH = os.path.join(OUTPUT_DIR, "concept_nodes_cache.json")

# ============================================================
# 网络请求
# ============================================================

def fetch_url(url, headers=None, timeout=20):
    if headers is None:
        headers = SINA_HEADERS
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode('utf-8')
        except Exception:
            if attempt < 2:
                try:
                    resp = urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)
                    return resp.read().decode('utf-8')
                except Exception:
                    time.sleep(1)
            else:
                raise

# ============================================================
# 新浪排名API — 获取股票列表
# ============================================================

def fetch_sina_ranking(node="hs_a", sort="changepercent", asc=0, page=1, num=100):
    """获取新浪股票排名数据"""
    url = (
        f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"Market_Center.getHQNodeData?page={page}&num={num}&sort={sort}&asc={asc}"
        f"&node={node}&symbol=&_s_r_a=sort"
    )
    text = fetch_url(url, SINA_HEADERS, timeout=15)
    data = json.loads(text)
    stocks = []
    for item in data:
        stocks.append({
            "code": item.get("code", ""),
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
            "price": float(item.get("trade", 0) or 0),
            "change_pct": float(item.get("changepercent", 0) or 0),
            "change_amt": float(item.get("pricechange", 0) or 0),
            "volume": float(item.get("volume", 0) or 0),
            "amount": float(item.get("amount", 0) or 0),
            "open": float(item.get("open", 0) or 0),
            "high": float(item.get("high", 0) or 0),
            "low": float(item.get("low", 0) or 0),
            "prev_close": float(item.get("settlement", 0) or 0),
            "turnover_rate": float(item.get("turnoverratio", 0) or 0),
            "total_mcap": float(item.get("mktcap", 0) or 0),  # 万元
            "circ_mcap": float(item.get("nmc", 0) or 0),  # 万元
            "pe": float(item.get("per", 0) or 0),
            "pb": float(item.get("pb", 0) or 0),
        })
    return stocks

def fetch_all_gainers(num_pages=8):
    """获取涨幅前N页股票（每页100只）"""
    all_stocks = []
    for page in range(1, num_pages + 1):
        stocks = fetch_sina_ranking(node="hs_a", sort="changepercent", asc=0, page=page, num=100)
        if not stocks:
            break
        all_stocks.extend(stocks)
        time.sleep(0.15)
    return all_stocks

def fetch_all_losers(num_pages=2):
    """获取跌幅前N页股票"""
    all_stocks = []
    for page in range(1, num_pages + 1):
        stocks = fetch_sina_ranking(node="hs_a", sort="changepercent", asc=1, page=page, num=100)
        if not stocks:
            break
        all_stocks.extend(stocks)
        time.sleep(0.15)
    return all_stocks

def fetch_sector_stocks(sector_node, num=50):
    """获取板块成分股（按涨幅降序）"""
    return fetch_sina_ranking(node=sector_node, sort="changepercent", asc=0, page=1, num=num)

# ============================================================
# 概念板块扫描（v1.3 新增）
# ============================================================

def fetch_concept_board_nodes():
    """从新浪 API 获取所有概念板块节点（chgn_ + gn_），带本地缓存。"""
    # 尝试从缓存加载
    if os.path.exists(CONCEPT_CACHE_PATH):
        try:
            with open(CONCEPT_CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("count", 0) > 500:  # 缓存有效
                return cached["nodes"]
        except Exception:
            pass

    # 从 API 获取
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
    text = fetch_url(url, timeout=25)
    data = json.loads(text)

    # 递归搜索所有 chgn_ 和 gn_ 节点
    concept_nodes = {}

    def _find_pairs(node):
        if isinstance(node, list) and len(node) >= 3:
            name = node[0] if isinstance(node[0], str) else None
            node_id = node[2] if isinstance(node[2], str) else None
            if name and node_id and (node_id.startswith("chgn_") or node_id.startswith("gn_")):
                concept_nodes[node_id] = name
            for item in node:
                if isinstance(item, list):
                    _find_pairs(item)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, list):
                    _find_pairs(item)

    _find_pairs(data)

    # 缓存到文件
    try:
        with open(CONCEPT_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"count": len(concept_nodes), "nodes": concept_nodes}, f, ensure_ascii=False)
    except Exception:
        pass

    return concept_nodes


def _fetch_one_concept(args):
    """获取单个概念板块的成分股（线程池 worker）。"""
    name, node_id = args
    try:
        url = (
            f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"Market_Center.getHQNodeData?page=1&num=100&sort=changepercent&asc=0"
            f"&node={node_id}&symbol=&_s_r_a=sort"
        )
        req = urllib.request.Request(url, headers=SINA_HEADERS)
        resp = urllib.request.urlopen(req, timeout=10, context=SSL_CTX)
        data = json.loads(resp.read().decode("utf-8"))
        return (name, node_id, data)
    except Exception:
        return (name, node_id, None)


def fetch_all_concept_boards(concept_nodes):
    """并发扫描所有概念板块，构建 code→concepts 映射 + 概念板块涨幅排名。

    返回:
        concept_data_list: 按 avg_change 降序排列的主题概念板块列表（已过滤非主题）
        code_to_concepts: {stock_code: [(concept_name, avg_change, lu_count), ...]}
    """
    pairs = list(concept_nodes.items())  # [(name, node_id), ...]
    # 修正：concept_nodes 是 {node_id: name}
    pairs = [(name, nid) for nid, name in concept_nodes.items()]

    all_results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_one_concept, p): p for p in pairs}
        for future in as_completed(futures):
            all_results.append(future.result())

    code_to_concepts = {}
    concept_data_list = []

    for name, nid, data in all_results:
        if not data:
            continue
        # 只统计主板非ST
        main_stocks = [
            s for s in data
            if is_main_board(s.get("code", "")) and not is_st(s.get("name", ""))
        ]
        if not main_stocks:
            continue

        avg_change = sum(safe_float(s.get("changepercent", 0)) for s in main_stocks) / len(main_stocks)
        lu_count = sum(1 for s in main_stocks if safe_float(s.get("changepercent", 0)) >= 9.8)
        strong_count = sum(1 for s in main_stocks if safe_float(s.get("changepercent", 0)) >= 5)

        # 过滤非主题概念
        if name in NON_THEMATIC_CONCEPTS:
            continue
        # 过滤成分股过少（<3）的概念（噪音）
        if len(main_stocks) < 3:
            continue

        concept_data_list.append({
            "name": name, "node": nid,
            "avg_change": round(avg_change, 2),
            "limit_up_count": lu_count,
            "strong_count": strong_count,
            "total_count": len(main_stocks),
        })

        for s in main_stocks:
            code = s.get("code", "")
            if not code:
                continue
            if code not in code_to_concepts:
                code_to_concepts[code] = []
            code_to_concepts[code].append((name, round(avg_change, 2), lu_count))

    # 按涨幅降序排名
    concept_data_list.sort(key=lambda x: x["avg_change"], reverse=True)
    for i, cd in enumerate(concept_data_list):
        cd["rank"] = i + 1

    return concept_data_list, code_to_concepts


def safe_float(v, default=0):
    """安全浮点转换。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def get_best_concept(code, code_to_concepts, concept_rank_map):
    """获取股票最热的主题概念板块。

    Args:
        code: 股票代码
        code_to_concepts: {code: [(name, avg_change, lu_count), ...]}
        concept_rank_map: {concept_name: rank}

    Returns:
        (concept_name, concept_rank, concept_data) 或 None
    """
    concepts = code_to_concepts.get(code, [])
    if not concepts:
        return None

    # 按 avg_change 降序取最热概念
    best = max(concepts, key=lambda x: x[1])
    cname = best[0]
    crank = concept_rank_map.get(cname, 999)

    return {
        "name": cname,
        "rank": crank,
        "avg_change": best[1],
        "limit_up_count": best[2],
        "strong_count": 0,  # 从概念数据列表中补充
    }

# ============================================================
# 新浪K线API
# ============================================================

def fetch_kline_sina(code, datalen=120):
    """从新浪获取日K线数据"""
    prefix = "sh" if code.startswith("6") else "sz"
    symbol = f"{prefix}{code}"
    url = (
        f"https://quotes.sina.cn/cn/api/json_v2.php/"
        f"CN_MarketDataService.getKLineData?"
        f"symbol={symbol}&scale=240&ma=no&datalen={datalen}"
    )
    text = fetch_url(url, SINA_HEADERS, timeout=15)
    data = json.loads(text)
    klines = []
    for item in data:
        klines.append({
            "date": item["day"],
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "volume": float(item["volume"]),
        })
    return klines

# ============================================================
# 过滤器
# ============================================================

def is_main_board(code):
    """主板（排除科创板688xxx和创业板300xxx/301xxx）"""
    if code.startswith("688"):
        return False
    if code.startswith("300") or code.startswith("301"):
        return False
    if code.startswith("8") or code.startswith("4"):
        return False  # 北交所/新三板
    if code.startswith("600") or code.startswith("601") or code.startswith("603") or code.startswith("605"):
        return True
    if code.startswith("000") or code.startswith("001") or code.startswith("002") or code.startswith("003"):
        return True
    return False

def is_st(name):
    return "ST" in name or "*ST" in name

# ============================================================
# 历史股性（核心信号：120日内涨停次数 + 历史最大连板高度）
# ============================================================

def analyze_history(klines):
    """分析120日K线内的涨停历史，返回涨停次数、最大连板高度、近期涨停信息。
    
    v1.2 新增：距上次涨停天数、近3/5/10日涨停次数、当前连板数，
    用于区分'有涨停基因但近期平静(首板前候选)'与'近期已涨停(降优先级)'。
    """
    if not klines or len(klines) < 10:
        return {
            "has_history": False, "limit_up_count": 0, "max_consecutive": 0,
            "has_2lianban": False, "days_since_last_lu": None,
            "lu_count_recent_3d": 0, "lu_count_recent_5d": 0, "lu_count_recent_10d": 0,
            "current_streak": 0,
        }
    consec = 0
    max_consec = 0
    lu_count = 0
    has = False
    last_lu_idx = -1
    lu_indices = []
    for i in range(1, len(klines)):
        pc = klines[i-1]["close"]
        if pc > 0 and (klines[i]["close"] - pc) / pc * 100 >= 9.8:
            consec += 1
            max_consec = max(max_consec, consec)
            lu_count += 1
            has = True
            last_lu_idx = i
            lu_indices.append(i)
        else:
            consec = 0

    n = len(klines)
    days_since_last = (n - 1 - last_lu_idx) if last_lu_idx >= 0 else None

    lu_recent_3d = sum(1 for idx in lu_indices if idx >= n - 3)
    lu_recent_5d = sum(1 for idx in lu_indices if idx >= n - 5)
    lu_recent_10d = sum(1 for idx in lu_indices if idx >= n - 10)

    # 当前连板数：从最后一根K线往前数连续涨停天数
    current_streak = 0
    for i in range(n - 1, 0, -1):
        pc = klines[i-1]["close"]
        if pc > 0 and (klines[i]["close"] - pc) / pc * 100 >= 9.8:
            current_streak += 1
        else:
            break

    return {
        "has_history": has,
        "limit_up_count": lu_count,
        "max_consecutive": max_consec,
        "has_2lianban": max_consec >= 2,
        "days_since_last_lu": days_since_last,
        "lu_count_recent_3d": lu_recent_3d,
        "lu_count_recent_5d": lu_recent_5d,
        "lu_count_recent_10d": lu_recent_10d,
        "current_streak": current_streak,
    }

# ============================================================
# 近期涨停状态与优先级（v1.2 核心：区分"首板前候选"与"近期已涨停"）
# ============================================================

def compute_recency_status(hist):
    """根据近期涨停情况计算优先级调整。
    
    核心逻辑：
    - P1 首板前候选：有涨停基因但近10日无涨停 → +5分（优先级最高）
    - P2 无涨停史：120日内无涨停 → +0分
    - P3 近期有涨停：近10日内有涨停 → -5分
    - P4 近期刚涨停：近5日内有涨停 → -10分
    - P5 近期已涨停：近3日内有涨停 → -18分（优先级最低）
    """
    recent_3d = hist.get("lu_count_recent_3d", 0)
    recent_5d = hist.get("lu_count_recent_5d", 0)
    recent_10d = hist.get("lu_count_recent_10d", 0)
    current_streak = hist.get("current_streak", 0)
    has_history = hist.get("has_history", False)
    days_since = hist.get("days_since_last_lu")

    # P5: 近3日有涨停或当前正在连板
    if current_streak >= 1 or recent_3d > 0:
        return {
            "tier": 5, "tier_label": "P5",
            "tag": "近期已涨停",
            "description": f"近3日有{recent_3d}次涨停/当前连板{current_streak}，降优先级",
            "score_adjust": -18,
        }

    # P4: 近5日有涨停
    if recent_5d > 0:
        return {
            "tier": 4, "tier_label": "P4",
            "tag": "近期刚涨停",
            "description": f"近5日有{recent_5d}次涨停，降优先级",
            "score_adjust": -10,
        }

    # P3: 近10日有涨停
    if recent_10d > 0:
        return {
            "tier": 3, "tier_label": "P3",
            "tag": "近期有涨停",
            "description": f"近10日有{recent_10d}次涨停，轻微降级",
            "score_adjust": -5,
        }

    # P1: 有涨停基因但近期平静——首板前候选，最高优先级
    if has_history and (days_since is None or days_since >= 10):
        d_str = f"近{days_since}日" if days_since is not None else "历史"
        return {
            "tier": 1, "tier_label": "P1",
            "tag": "首板前候选",
            "description": f"有涨停基因({d_str}无涨停)，首板前候选优先",
            "score_adjust": 5,
        }

    # P2: 无涨停史
    return {
        "tier": 2, "tier_label": "P2",
        "tag": "无涨停史",
        "description": "120日内无涨停记录",
        "score_adjust": 0,
    }

# ============================================================
# 因子1: 情绪环境（5分，降为开关/系数）
# ============================================================

def compute_market_sentiment(gainers, losers):
    main_board = [s for s in gainers if is_main_board(s["code"]) and not is_st(s["name"])]
    
    limit_up = [s for s in main_board if s["change_pct"] >= 9.8]
    limit_down = [s for s in losers if is_main_board(s["code"]) and not is_st(s["name"]) and s["change_pct"] <= -9.8]
    strong = [s for s in main_board if s["change_pct"] >= 7.0]
    
    # 炸板率
    hit_limit = [s for s in main_board if s["prev_close"] > 0 and s["high"] / s["prev_close"] >= 1.098]
    not_closed = [s for s in hit_limit if s["change_pct"] < 9.8]
    explosion_rate = len(not_closed) / len(hit_limit) * 100 if hit_limit else 0
    
    if len(limit_up) > 50 and explosion_rate < 40:
        max_boards = 4
    elif len(limit_up) > 30 and explosion_rate < 50:
        max_boards = 3
    elif len(limit_up) > 15:
        max_boards = 2
    else:
        max_boards = 1
    
    sentiment_score = round(lu_count_to_score(len(limit_up)) + explosion_to_score(explosion_rate) + strong_to_score(len(strong)), 1)
    
    if sentiment_score <= 30: label = "冰点"
    elif sentiment_score <= 50: label = "弱势"
    elif sentiment_score <= 70: label = "正常"
    elif sentiment_score <= 85: label = "强势"
    else: label = "极热"
    
    return {
        "limit_up_count": len(limit_up),
        "limit_down_count": len(limit_down),
        "strong_count": len(strong),
        "explosion_rate": round(explosion_rate, 1),
        "max_boards_est": max_boards,
        "sentiment_score": sentiment_score,
        "sentiment_label": label,
        "is_ice_point": len(limit_up) < 15,  # 极端冰点开关
    }

def lu_count_to_score(n):
    return min(40, n / 100 * 40)

def explosion_to_score(rate):
    return max(0, 30 - rate / 70 * 30)

def strong_to_score(n):
    return min(30, n / 200 * 30)

def score_sentiment_coefficient(sentiment):
    """情绪环境 v1.1：降为开关/系数。
    常态：所有股票同得 5 分（不参与个股排序）。
    极端冰点（涨停<15家）：得 0 分，并对总分施加 ×0.9 降权系数。"""
    if sentiment.get("is_ice_point", False):
        return 0, 0.9, {"状态": "冰点降权×0.9", "得分": 0}
    return 5, 1.0, {"状态": "常态(不参与排序)", "得分": 5}

# ============================================================
# 因子2: 板块强度（10分，v1.1 从20分降至10分）
# ============================================================

def score_sector_strength(sector_data, sector_rank):
    if sector_rank <= 3: rank_score = 4
    elif sector_rank <= 5: rank_score = 3
    elif sector_rank <= 10: rank_score = 2
    elif sector_rank <= 20: rank_score = 1
    else: rank_score = 0
    
    change = sector_data["avg_change"]
    if change >= 4: change_score = 3
    elif change >= 2.5: change_score = 2
    elif change >= 1.5: change_score = 1.5
    elif change >= 0.5: change_score = 1
    else: change_score = 0
    
    lu = sector_data["limit_up_count"]
    if lu >= 5: lu_score = 3
    elif lu >= 3: lu_score = 2
    elif lu >= 1: lu_score = 1
    else: lu_score = 0
    
    total = min(10, rank_score + change_score + lu_score)
    return total, {"排名": rank_score, "涨幅": change_score, "涨停数": lu_score}

# ============================================================
# 因子3: 题材催化（10分，v1.1 从20分降至10分）
# ============================================================

def score_theme_catalyst(sector_data, sector_rank):
    if sector_rank <= 3: hot_score = 4
    elif sector_rank <= 5: hot_score = 3
    elif sector_rank <= 10: hot_score = 2
    elif sector_rank <= 15: hot_score = 1
    else: hot_score = 0
    
    change = sector_data["avg_change"]
    if change >= 5: strength = 3
    elif change >= 3: strength = 2
    elif change >= 1.5: strength = 1
    else: strength = 0
    
    lu = sector_data["limit_up_count"]
    if lu >= 5: echelon = 3
    elif lu >= 3: echelon = 2
    elif lu >= 1: echelon = 1
    else: echelon = 0
    
    total = min(10, hot_score + strength + echelon)
    return total, {"热点排名": hot_score, "涨幅强度": strength, "涨停梯队": echelon}

# ============================================================
# 因子4: 个股辨识度（25分，v1.1 从15分升至25分）
# 核心子项：120日内涨停次数 + 历史最大连板高度（≥15分，占因子60%+）
# ============================================================

def score_stock_recognition(stock, sector_stocks, hist):
    # === 历史股性子项（15分） ===
    lu_count = hist.get("limit_up_count", 0)
    max_consec = hist.get("max_consecutive", 0)
    
    # 120日内涨停次数（10分）
    if lu_count >= 8: lu_hist = 10
    elif lu_count >= 5: lu_hist = 8
    elif lu_count >= 3: lu_hist = 6
    elif lu_count >= 1: lu_hist = 4
    else: lu_hist = 0
    
    # 历史最大连板高度（5分）
    if max_consec >= 4: consec_hist = 5
    elif max_consec >= 3: consec_hist = 4
    elif max_consec >= 2: consec_hist = 3
    elif max_consec >= 1: consec_hist = 2
    else: consec_hist = 0
    
    history_score = lu_hist + consec_hist  # 最多15分
    
    # === 涨幅排名（5分） ===
    sorted_by_gain = sorted(sector_stocks, key=lambda x: x["change_pct"], reverse=True)
    rank = next((i+1 for i, s in enumerate(sorted_by_gain) if s["code"] == stock["code"]), len(sorted_by_gain))
    
    if rank <= 3: gain_rank = 5
    elif rank <= 5: gain_rank = 4
    elif rank <= 10: gain_rank = 2
    elif rank <= 20: gain_rank = 1
    else: gain_rank = 0
    
    # === 成交活跃（5分） ===
    amt = stock.get("amount", 0)
    if amt >= 10e8: activity = 5
    elif amt >= 5e8: activity = 4
    elif amt >= 2e8: activity = 3
    elif amt >= 1e8: activity = 2
    elif amt >= 0.5e8: activity = 1
    else: activity = 0
    
    total = min(25, history_score + gain_rank + activity)
    detail = {
        "涨停次数分": lu_hist, "连板高度分": consec_hist,
        "涨幅排名": gain_rank, "成交活跃": activity,
        "lu_count_120d": lu_count, "max_consec": max_consec,
    }
    return total, detail

# ============================================================
# 因子5: 资金预热（20分，v1.1 从15分升至20分）
# ============================================================

def score_capital_preheat(klines):
    if not klines or len(klines) < 20:
        return 0, {"说明": "数据不足"}, {}
    
    n = len(klines)
    vols = [k["volume"] for k in klines]
    closes = [k["close"] for k in klines]
    
    vol_ma20 = sum(vols[-20:]) / 20
    vol_5d = sum(vols[-5:]) / 5
    
    # 1. 成交量温和放大（6分）
    ratio_5d_20d = vol_5d / vol_ma20 if vol_ma20 > 0 else 0
    if 1.2 <= ratio_5d_20d <= 2.5: warm = 6
    elif 1.1 <= ratio_5d_20d <= 3.0: warm = 4
    elif ratio_5d_20d > 1.0: warm = 2
    else: warm = 0
    
    # 2. 连续上涨（4分）
    up_days = sum(1 for i in range(-3, 0) if n+i > 0 and closes[i] > closes[i-1]) if n >= 4 else 0
    if up_days >= 3: inflow = 4
    elif up_days >= 2: inflow = 3
    elif up_days >= 1: inflow = 1
    else: inflow = 0
    
    # 3. 涨时放量（4分）
    up_vols = [vols[i] for i in range(-5, 0) if n+i > 0 and n+i-1 >= 0 and closes[i] > closes[i-1]]
    dn_vols = [vols[i] for i in range(-5, 0) if n+i > 0 and n+i-1 >= 0 and closes[i] <= closes[i-1]]
    avg_up = sum(up_vols)/len(up_vols) if up_vols else 0
    avg_dn = sum(dn_vols)/len(dn_vols) if dn_vols else 0
    
    if avg_up > 0 and avg_dn > 0:
        if avg_up > avg_dn * 1.2: pu_vol = 4
        elif avg_up > avg_dn: pu_vol = 2
        else: pu_vol = 0
    elif avg_up > 0: pu_vol = 2
    else: pu_vol = 0
    
    # 4. 回调缩量（3分）
    if avg_dn > 0 and vol_ma20 > 0:
        if avg_dn < vol_ma20 * 0.8: pullback = 3
        elif avg_dn < vol_ma20: pullback = 2
        else: pullback = 0
    else: pullback = 1
    
    # 5. 大单异动（3分）
    today_vol = vols[-1]
    vol_5d_avg = sum(vols[-6:-1]) / 5 if n >= 6 else vol_ma20
    ratio_today = today_vol / vol_5d_avg if vol_5d_avg > 0 else 0
    if ratio_today >= 2.0: big = 3
    elif ratio_today >= 1.5: big = 2
    elif ratio_today >= 1.2: big = 1
    else: big = 0
    
    total = min(20, warm + inflow + pu_vol + pullback + big)
    signals = {
        "vol_ratio_5d_20d": round(ratio_5d_20d, 2),
        "vol_ratio_today": round(ratio_today, 2),
        "up_days_recent3": up_days,
    }
    return total, {"量放大(6)": warm, "净流入(4)": inflow, "涨放量(4)": pu_vol, "跌缩量(3)": pullback, "大单(3)": big}, signals

# ============================================================
# 因子6: K线/筹码（15分，v1.1 重写）
# 删除横盘蓄势（反向指标），改奖励趋势/均线多头，惩罚距高点过远
# ============================================================

def score_kline_chip(klines):
    if not klines or len(klines) < 25:
        return 0, {"说明": "数据不足"}, {}
    
    n = len(klines)
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    current = closes[-1]
    
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    
    # 1. 站上均线（5分）
    ma_score = 0
    if current > ma5: ma_score += 1.5
    if current > ma10: ma_score += 1.5
    if current > ma20: ma_score += 2
    
    # 2. 均线多头排列（4分）：MA5>MA10>MA20
    if ma5 > ma10 > ma20: multi_align = 4
    elif ma5 > ma10: multi_align = 2
    else: multi_align = 0
    
    # 3. 近20日涨幅为正（4分）：趋势动能
    if n >= 21:
        gain_20d = (current - closes[-21]) / closes[-21] * 100 if closes[-21] > 0 else 0
    else:
        gain_20d = (current - closes[0]) / closes[0] * 100 if closes[0] > 0 else 0
    if gain_20d >= 10: trend = 4
    elif gain_20d >= 5: trend = 3
    elif gain_20d > 0: trend = 2
    else: trend = 0
    
    # 4. 位置（2分）：距60日高点
    high_60d = max(highs[-60:]) if n >= 60 else max(highs)
    dist = (high_60d - current) / high_60d * 100 if high_60d > 0 else 100
    if dist <= 5: pos = 2
    elif dist <= 10: pos = 1.5
    elif dist <= 20: pos = 1
    else: pos = 0  # 距高点>20% 不给分（惩罚过远）
    
    total = min(15, ma_score + multi_align + trend + pos)
    signals = {
        "price": round(current, 2), "ma5": round(ma5, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2),
        "above_ma5": current > ma5, "above_ma10": current > ma10, "above_ma20": current > ma20,
        "multi_align": ma5 > ma10 > ma20,
        "gain_20d": round(gain_20d, 1), "dist_to_high": round(dist, 1),
    }
    return total, {"均线(5)": round(ma_score,1), "多头排列(4)": multi_align, "趋势动能(4)": trend, "位置(2)": round(pos,1)}, signals

# ============================================================
# 因子7: 市值/流动性（15分，v1.1 从10分升至15分，去小市值偏好）
# 取消40-100亿加分，只奖励换手率5-15%健康区间，市值仅作流动性辅助
# ============================================================

def score_market_cap_liquidity(stock):
    circ = stock.get("circ_mcap", 0) / 10000  # 万元→亿
    turnover = stock.get("turnover_rate", 0)
    
    # 换手率健康区间（10分）—— v1.1 核心
    if 5 <= turnover <= 15: tr = 10
    elif 3 <= turnover < 5 or 15 < turnover <= 20: tr = 7
    elif 1 <= turnover < 3 or 20 < turnover <= 30: tr = 4
    elif turnover > 30: tr = 2  # 过度投机
    else: tr = 0  # 换手率过低
    
    # 市值流动性辅助（5分）—— 不偏好小市值，只惩罚极端值
    if 50 <= circ <= 300: cap = 5   # 流动性充足的主板区间
    elif 20 <= circ < 50: cap = 3   # 偏小但可接受
    elif circ > 300: cap = 2        # 大盘股流动性好但连板难
    else: cap = 0
    
    return min(15, cap + tr), {"换手率(10)": tr, "市值辅助(5)": cap, "circ_yi": round(circ,1), "turnover": round(turnover,2)}

# ============================================================
# 三共振硬过滤（历史股性 + 趋势 + 量能）
# ============================================================

def check_three_resonance(hist, kl_sig, cap_sig):
    """三共振：历史股性(120日内有涨停) + 趋势(站上MA20) + 量能(5d/20d≥1.2)"""
    r_history = hist.get("has_history", False)
    r_trend = kl_sig.get("above_ma20", False)
    r_volume = cap_sig.get("vol_ratio_5d_20d", 0) >= 1.2
    resonance_count = sum([r_history, r_trend, r_volume])
    return {
        "all_three": r_history and r_trend and r_volume,
        "count": resonance_count,
        "r_history": r_history,
        "r_trend": r_trend,
        "r_volume": r_volume,
    }

# ============================================================
# 分级与分类（v1.1 门槛下调 + 三共振硬过滤）
# ============================================================

def get_pool(adjusted_total, resonance):
    """v1.2: 入池基于调整后分数（含近期涨停调整）"""
    if adjusted_total >= 65 and resonance["all_three"]:
        return "重点观察"
    elif adjusted_total >= 60:
        return "预备池"
    elif adjusted_total >= 50:
        return "观察池"
    else:
        return "淘汰"

def get_grade(scores, resonance, adjusted_total=None):
    """v1.2: 分级基于调整后分数"""
    total = adjusted_total if adjusted_total is not None else scores["total"]
    if total >= 65 and resonance["all_three"] and scores["stock_recognition"] >= 18 and scores["capital_preheat"] >= 14:
        return "A"
    if total >= 60 and resonance["count"] >= 2:
        return "B"
    if total >= 50:
        return "C"
    return "D"

def lianban_prob(scores):
    t = scores["theme_catalyst"] / 10
    r = scores["stock_recognition"] / 25
    c = scores["capital_preheat"] / 20
    s = scores["sentiment"] / 5
    k = scores["kline_chip"] / 15
    return round(t * r * c * s * k * 100, 1)

def next_day_watch(ks, cs, stock, hist, recency=None):
    signals = []
    # v1.2: 优先级标签
    if recency:
        if recency["tier"] == 1:
            signals.append(f"★首板前候选({recency['tag']})")
        elif recency["tier"] >= 4:
            signals.append(f"⚠{recency['tag']}")
    if hist.get("has_history"): signals.append("历史股性活跃")
    if hist.get("has_2lianban"): signals.append(f"曾{hist.get('max_consecutive')}连板")
    # v1.2: 近期涨停天数
    dsl = hist.get("days_since_last_lu")
    if dsl is not None:
        signals.append(f"距上次涨停{dsl}日")
    if ks.get("above_ma20"): signals.append("站上MA20")
    if ks.get("multi_align"): signals.append("均线多头排列")
    if ks.get("gain_20d", 0) > 0: signals.append("近20日上涨")
    if cs.get("vol_ratio_5d_20d", 0) >= 1.2: signals.append("近期量能放大")
    if cs.get("vol_ratio_today", 0) >= 1.5: signals.append("放量异动")
    if cs.get("up_days_recent3", 0) >= 2: signals.append("连续上涨")
    if not signals: signals.append("等待信号确认")
    return signals

# ============================================================
# 主流程
# ============================================================

def main():
    start = time.time()
    now = datetime.now(timezone(timedelta(hours=8)))  # 固定北京时间（GitHub runner 是 UTC）
    print(f"{'='*70}")
    print(f"  连板潜力七因子选股系统 v1.2")
    print(f"  扫描时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    
    # === Phase 1: 全市场行情 ===
    print("\n[1/6] 获取全市场行情...")
    gainers = fetch_all_gainers(num_pages=8)
    losers = fetch_all_losers(num_pages=2)
    print(f"  涨幅榜: {len(gainers)} 只 | 跌幅榜: {len(losers)} 只")
    
    # === Phase 2: 市场情绪 ===
    print("\n[2/6] 计算市场情绪...")
    sentiment = compute_market_sentiment(gainers, losers)
    print(f"  涨停: {sentiment['limit_up_count']} | 跌停: {sentiment['limit_down_count']} | "
          f"炸板率: {sentiment['explosion_rate']}% | 情绪: {sentiment['sentiment_score']}({sentiment['sentiment_label']})"
          f" | 冰点: {sentiment['is_ice_point']}")
    
    # === Phase 3: 申万行业板块扫描 ===
    print("\n[3/7] 扫描申万行业板块...")
    sector_data_list = []
    code_to_sw_industry = {}  # v1.3: code -> (sector_name, sector_rank, sector_data)
    for node, name in SW_SECTORS:
        try:
            stocks = fetch_sector_stocks(node, num=500)
            time.sleep(0.15)
            main_stocks = [s for s in stocks if is_main_board(s["code"]) and not is_st(s["name"])]
            if not main_stocks:
                continue
            # v1.3: 构建完整的 code→行业映射（不限 top 15）
            for s in main_stocks:
                code_to_sw_industry[s["code"]] = name
            avg_change = sum(s["change_pct"] for s in main_stocks) / len(main_stocks)
            lu_count = sum(1 for s in main_stocks if s["change_pct"] >= 9.8)
            strong_count = sum(1 for s in main_stocks if s["change_pct"] >= 5)
            up_count = sum(1 for s in main_stocks if s["change_pct"] > 0)
            sector_data_list.append({
                "name": name, "node": node,
                "avg_change": round(avg_change, 2),
                "limit_up_count": lu_count,
                "strong_count": strong_count,
                "up_count": up_count,
                "total_count": len(main_stocks),
                "stocks": main_stocks,
            })
            print(f"  [{name}] {len(main_stocks)}只 | 均涨:{avg_change:+.2f}% | 涨停:{lu_count} | 强势:{strong_count}")
        except Exception as e:
            print(f"  [{name}] 获取失败: {e}")
    
    sector_data_list.sort(key=lambda x: x["avg_change"], reverse=True)
    for i, sd in enumerate(sector_data_list):
        sd["rank"] = i + 1
    
    print(f"\n  申万行业扫描完成: {len(sector_data_list)} 个板块, 行业映射覆盖 {len(code_to_sw_industry)} 只股票")

    # === Phase 3.5: 概念板块扫描（v1.3 新增）===
    print("\n[3.5/7] 扫描概念板块（并发）...")
    concept_nodes = fetch_concept_board_nodes()
    print(f"  概念板块节点: {len(concept_nodes)} 个")
    concept_data_list, code_to_concepts = fetch_all_concept_boards(concept_nodes)
    concept_rank_map = {cd["name"]: cd["rank"] for cd in concept_data_list}
    print(f"  主题概念板块: {len(concept_data_list)} 个 | 个股概念映射: {len(code_to_concepts)} 只")
    if concept_data_list:
        top5 = " | ".join(f"{cd['name']}({cd['avg_change']:+.1f}%)" for cd in concept_data_list[:5])
        print(f"  Top 5 热门概念: {top5}")
    
    # === Phase 4: 候选股筛选 ===
    print("\n[4/7] 筛选候选股...")
    candidates = []
    seen = set()
    
    # 构建 sector_data 查找映射
    sw_sector_map = {sd["name"]: sd for sd in sector_data_list}
    
    for sd in sector_data_list[:15]:
        for s in sd["stocks"]:
            code = s["code"]
            if code in seen:
                continue
            if not is_main_board(code) or is_st(s["name"]):
                continue
            if s["price"] <= 0:
                continue
            circ = s.get("circ_mcap", 0) / 10000
            if circ < 20 or circ > 300:
                continue
            if s["change_pct"] < -2 or s["change_pct"] > 9.8:
                continue
            seen.add(code)
            s["sector_name"] = sd["name"]
            s["sector_rank"] = sd["rank"]
            s["sector_data"] = sd
            # v1.3: 查概念板块
            best_concept = get_best_concept(code, code_to_concepts, concept_rank_map)
            s["concept_name"] = best_concept["name"] if best_concept else None
            s["concept_rank"] = best_concept["rank"] if best_concept else 999
            s["concept_data"] = best_concept if best_concept else None
            candidates.append(s)
    
    for s in gainers[:100]:
        code = s["code"]
        if code in seen:
            continue
        if not is_main_board(code) or is_st(s["name"]) or s["change_pct"] < 5:
            continue
        circ = s.get("circ_mcap", 0) / 10000
        if 20 <= circ <= 300:
            # v1.3: 从映射查申万行业（消除"未分类"）
            sw_name = code_to_sw_industry.get(code, "未分类")
            if sw_name != "未分类" and sw_name in sw_sector_map:
                sw_sd = sw_sector_map[sw_name]
                s["sector_name"] = sw_name
                s["sector_rank"] = sw_sd["rank"]
                s["sector_data"] = sw_sd
            else:
                # 行业映射也找不到，用空数据兜底（极少情况）
                s["sector_name"] = sw_name
                s["sector_rank"] = 50
                s["sector_data"] = {"avg_change": 0, "limit_up_count": 0, "strong_count": 0}
            # v1.3: 查概念板块
            best_concept = get_best_concept(code, code_to_concepts, concept_rank_map)
            s["concept_name"] = best_concept["name"] if best_concept else None
            s["concept_rank"] = best_concept["rank"] if best_concept else 999
            s["concept_data"] = best_concept if best_concept else None
            candidates.append(s)
            seen.add(code)
    
    candidates.sort(key=lambda x: x["change_pct"], reverse=True)
    if len(candidates) > 120:
        candidates = candidates[:120]
    
    # v1.3: 统计分类情况
    unclassified = sum(1 for c in candidates if c.get("sector_name") == "未分类")
    has_concept = sum(1 for c in candidates if c.get("concept_name"))
    print(f"  总候选: {len(candidates)} 只 | 未分类: {unclassified} | 有概念: {has_concept}")
    
    # === Phase 5: K线分析 + 七因子评分 ===
    print(f"\n[5/7] K线分析 + 七因子评分 v1.3（{len(candidates)}只）...")
    results = []
    failed = []
    
    # 情绪系数（本轮全局，所有股票相同）
    sent_s_flat, sent_coeff, sent_detail = score_sentiment_coefficient(sentiment)
    
    for i, stock in enumerate(candidates):
        code = stock["code"]
        name = stock["name"]
        pct = (i+1) / len(candidates) * 100
        print(f"\r  [{pct:5.1f}%] ({i+1}/{len(candidates)}) {code} {name}      ", end="", flush=True)
        
        try:
            klines = fetch_kline_sina(code, datalen=120)
            time.sleep(0.12)
            if len(klines) < 20:
                raise ValueError(f"K线不足: {len(klines)}")
            
            # v1.3: 优先用概念板块数据评分，回退申万行业
            concept = stock.get("concept_data")
            sw_sd = stock.get("sector_data", {})
            sw_sr = stock.get("sector_rank", 50)
            
            if concept:
                # 用概念板块数据
                scoring_sd = concept
                scoring_sr = concept.get("rank", 999)
            else:
                # 回退申万行业
                scoring_sd = sw_sd
                scoring_sr = sw_sr
            
            # 历史股性分析
            hist = analyze_history(klines)
            
            # 七因子评分 v1.3
            theme_s, theme_d = score_theme_catalyst(scoring_sd, scoring_sr)
            sec_s, sec_d = score_sector_strength(scoring_sd, scoring_sr)
            
            same_sec = stock.get("sector_data", {}).get("stocks", [stock])
            rec_s, rec_d = score_stock_recognition(stock, same_sec, hist)
            
            cap_s, cap_d, cap_sig = score_capital_preheat(klines)
            kl_s, kl_d, kl_sig = score_kline_chip(klines)
            mc_s, mc_d = score_market_cap_liquidity(stock)
            sent_s = sent_s_flat
            
            total = round(theme_s + sec_s + rec_s + cap_s + kl_s + mc_s + sent_s, 1)
            # 冰点整体降权
            if sent_coeff < 1.0:
                total = round(total * sent_coeff, 1)
            
            scores = {
                "theme_catalyst": theme_s, "sector_strength": sec_s,
                "stock_recognition": rec_s, "capital_preheat": cap_s,
                "kline_chip": kl_s, "market_cap_liquidity": mc_s,
                "sentiment": sent_s, "total": total,
            }
            
            # 三共振硬过滤
            resonance = check_three_resonance(hist, kl_sig, cap_sig)
            
            # v1.2: 近期涨停调整
            recency = compute_recency_status(hist)
            adjusted_total = round(total + recency["score_adjust"], 1)
            
            # v1.3: 获取所有概念标签
            all_concepts = code_to_concepts.get(code, [])
            concept_names = [c[0] for c in sorted(all_concepts, key=lambda x: -x[1])[:5]]
            
            results.append({
                "code": code, "name": name,
                "sector": stock.get("concept_name") or stock.get("sector_name", "未分类"),  # v1.3: 优先显示概念
                "sw_industry": stock.get("sector_name", "未分类"),  # v1.3: 保留行业分类
                "concept": stock.get("concept_name"),  # v1.3: 概念板块
                "concept_rank": stock.get("concept_rank", 999),
                "all_concepts": concept_names,  # v1.3: 所有概念标签（top 5）
                "sector_rank": scoring_sr,
                "price": stock["price"],
                "change_pct": stock["change_pct"],
                "turnover_rate": round(stock.get("turnover_rate", 0), 2),
                "circ_mcap_yi": round(stock.get("circ_mcap", 0) / 10000, 1),
                "amount_yi": round(stock.get("amount", 0) / 1e8, 2),
                "scores": scores,
                "adjusted_total": adjusted_total,
                "recency": recency,
                "score_details": {
                    "题材催化(/10)": theme_d, "板块强度(/10)": sec_d,
                    "个股辨识度(/25)": rec_d, "资金预热(/20)": cap_d,
                    "K线筹码(/15)": kl_d, "市值流动性(/15)": mc_d,
                    "情绪环境(/5)": sent_detail,
                    "近期涨停调整": recency["score_adjust"],
                },
                "scoring_source": "concept" if concept else "sw_industry",  # v1.3: 标记评分来源
                "pool": get_pool(adjusted_total, resonance),
                "grade": get_grade(scores, resonance, adjusted_total),
                "lianban_probability": lianban_prob(scores),
                "kline_signals": kl_sig,
                "capital_signals": cap_sig,
                "history": hist,
                "resonance": resonance,
                "next_day_watch": next_day_watch(kl_sig, cap_sig, stock, hist, recency),
            })
        except Exception as e:
            failed.append({"code": code, "name": name, "error": str(e)})
        
        if time.time() - start > 480:
            print(f"\n  ⚠ 已运行{time.time()-start:.0f}秒，保存进度退出")
            break
    
    # === Phase 6: 输出 ===
    print(f"\n\n[6/7] 生成结果...")
    # v1.2: 先按优先级层级(P1首板前>P2无涨停史>P3近10日>P4近5日>P5近3日)，再按调整后分数
    results.sort(key=lambda x: (x["recency"]["tier"], -x["adjusted_total"]))
    
    pool_cnt = {"重点观察":0, "预备池":0, "观察池":0, "淘汰":0}
    grade_cnt = {"A":0, "B":0, "C":0, "D":0}
    for r in results:
        pool_cnt[r["pool"]] = pool_cnt.get(r["pool"], 0) + 1
        grade_cnt[r["grade"]] = grade_cnt.get(r["grade"], 0) + 1
    
    output = {
        "scan_date": now.strftime("%Y-%m-%d"),
        "scan_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "system_version": "v1.3",
        "model": "连板潜力七因子模型 v1.3（概念板块分类 + 行业映射补全）",
        "weight_config": {
            "个股辨识度": 25, "资金预热": 20, "K线筹码": 15,
            "题材催化": 10, "板块强度": 10, "市值流动性": 15, "情绪环境": 5,
        },
        "threshold": {"重点观察": "≥65分+三共振", "预备池": "≥60分", "观察池": "≥50分", "淘汰": "<50分"},
        "market_sentiment": sentiment,
        "sector_rankings": [
            {
                "rank": sd["rank"], "name": sd["name"],
                "avg_change": sd["avg_change"],
                "limit_up_count": sd["limit_up_count"],
                "strong_count": sd["strong_count"],
                "up_count": sd["up_count"],
                "total_count": sd["total_count"],
            }
            for sd in sector_data_list[:30]
        ],
        "concept_rankings": [  # v1.3: 概念板块排名
            {
                "rank": cd["rank"], "name": cd["name"],
                "avg_change": cd["avg_change"],
                "limit_up_count": cd["limit_up_count"],
                "strong_count": cd["strong_count"],
                "total_count": cd["total_count"],
            }
            for cd in concept_data_list[:50]
        ],
        "candidates": results,
        "summary": {
            "total_scanned": len(results),
            "total_failed": len(failed),
            "pool_distribution": pool_cnt,
            "grade_distribution": grade_cnt,
            "unclassified_count": sum(1 for r in results if r.get("sw_industry") == "未分类"),
            "concept_covered": sum(1 for r in results if r.get("concept")),
            "concept_scoring_count": sum(1 for r in results if r.get("scoring_source") == "concept"),
        },
        "failed": failed[:20],
        "elapsed_seconds": round(time.time() - start, 1),
    }
    
    output_path = os.path.join(OUTPUT_DIR, f"seven_factor_{now.strftime('%Y-%m-%d')}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    latest_path = os.path.join(OUTPUT_DIR, "seven_factor_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*70}")
    print(f"  完成！耗时 {output['elapsed_seconds']}秒")
    print(f"  候选: {len(results)} | 失败: {len(failed)}")
    print(f"  重点观察: {pool_cnt['重点观察']} | 预备: {pool_cnt['预备池']} | 观察: {pool_cnt['观察池']} | 淘汰: {pool_cnt['淘汰']}")
    print(f"  A: {grade_cnt['A']} | B: {grade_cnt['B']} | C: {grade_cnt['C']} | D: {grade_cnt['D']}")
    print(f"  v1.3: 未分类={output['summary']['unclassified_count']} | 概念覆盖={output['summary']['concept_covered']}/{len(results)} | 概念评分={output['summary']['concept_scoring_count']}")
    
    # v1.2: 按优先级层级统计
    tier_cnt = {}
    for r in results:
        t = r["recency"]["tier_label"]
        tier_cnt[t] = tier_cnt.get(t, 0) + 1
    print(f"  优先级: {' | '.join(f'{k}:{v}' for k, v in sorted(tier_cnt.items()))}")
    
    key = [r for r in results if r["pool"] == "重点观察"]
    if key:
        print(f"\n  ★ 重点观察池（{len(key)}只，≥65分+三共振，按优先级排序）")
        for r in key[:15]:
            concept_str = f"概念:{r.get('concept','无')}" if r.get('concept') else f"行业:{r.get('sw_industry','?')}"
            print(f"  {r['code']} {r['name']:8s} | {r['recency']['tier_label']} {r['recency']['tag']} | "
                  f"调整分:{r['adjusted_total']:5.1f}(原{r['scores']['total']}) | "
                  f"涨幅:{r['change_pct']:+.1f}% | {concept_str} | 共振:{r['resonance']['count']}/3")
    
    print(f"\n  结果: {output_path}")
    print(f"{'='*70}")

    # === 同步部署到 Netlify ===
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from netlify_deploy import run as netlify_run
        netlify_run()
    except Exception as e:
        print(f"[Netlify] 部署失败（不影响本地数据）: {e}")

    return output

if __name__ == "__main__":
    main()
