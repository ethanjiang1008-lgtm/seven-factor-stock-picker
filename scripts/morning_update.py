#!/usr/bin/env python3
"""08:00 morning update layer.
Fetches overnight headlines and produces a qualitative adjustment layer.
It never overwrites seven-factor scores or the candidate pool.
"""
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,"data")
EVENING=os.path.join(DATA,"evening_latest.json")
OUT=os.path.join(DATA,"morning_latest.json")

def fetch(url, timeout=15):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read()

def rss(query):
    url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":query,"hl":"zh-CN","gl":"CN","ceid":"CN:zh-Hans"})
    try:
        root=ET.fromstring(fetch(url))
        out=[]
        for item in root.findall(".//item")[:10]:
            title=(item.findtext("title") or "").strip()
            link=(item.findtext("link") or "").strip()
            pub=(item.findtext("pubDate") or "").strip()
            if title: out.append({"title":title,"link":link,"pubDate":pub})
        return out
    except Exception as e:
        return [{"title":f"RSS抓取失败: {e}","link":"","pubDate":""}]

def main():
    evening={}
    if os.path.exists(EVENING):
        with open(EVENING,"r",encoding="utf-8") as f: evening=json.load(f)
    queries=["美股 隔夜 市场", "纳斯达克 标普 道琼斯", "黄金 原油 美债 美元", "中国 政策 产业链 隔夜", "A股 今日 早盘 消息", "科技 AI 机器人 半导体 新能源 医药"]
    overnight=[]
    for q in queries: overnight.extend(rss(q)[:8])
    focus=evening.get("focus_candidates",[])
    output={
        "generated_at":datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "source_evening_at":evening.get("generated_at"),
        "focus_candidates":focus,
        "overnight_headlines":overnight[:50],
        "market_checks":{
            "us_market":"待从隔夜数据源进一步量化",
            "commodities":"待从隔夜数据源进一步量化",
            "policy_and_industry":"重点关注消息是否改变昨日主线逻辑",
        },
        "adjustment_rules":[
            "重大利空/主线逻辑被证伪：候选降级或移出今日观察",
            "重大产业催化/政策强化主线：候选优先级上调，但不直接改变七因子分数",
            "没有足够证据：保持昨日结论，等待9:25竞价验证",
        ],
        "notes":["08:00只修正预期，不重新计算七因子。","最终是否可交易交由竞价与盘中确认。"],
    }
    with open(OUT,"w",encoding="utf-8") as f: json.dump(output,f,ensure_ascii=False,indent=2)
    print(f"[Morning] generated {OUT}; focus={len(focus)}, overnight={len(overnight[:50])}")

if __name__=="__main__": main()
