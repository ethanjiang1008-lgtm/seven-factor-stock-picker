#!/usr/bin/env python3
"""20:00 evening analysis layer.
Uses the existing closing candidate pool plus fresh RSS headlines.
Does not change seven-factor scores.
"""
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LATEST = os.path.join(DATA, "seven_factor_latest.json")
OUT = os.path.join(DATA, "evening_latest.json")

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def google_news_rss(query, hl="zh-CN", gl="CN", ceid="CN:zh-Hans"):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": hl, "gl": gl, "ceid": ceid})
    try:
        root = ET.fromstring(fetch(url))
        items=[]
        for item in root.findall(".//item")[:10]:
            title=(item.findtext("title") or "").strip()
            link=(item.findtext("link") or "").strip()
            pub=(item.findtext("pubDate") or "").strip()
            if title:
                items.append({"title": title, "link": link, "pubDate": pub})
        return items
    except Exception as e:
        return [{"title": f"RSS抓取失败: {e}", "link": "", "pubDate": ""}]

def load_latest():
    with open(LATEST, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    data=load_latest()
    cands=data.get("candidates") or []
    focus=[x for x in cands if x.get("pool")=="重点观察"]
    focus=sorted(focus,key=lambda x:(x.get("recency",{}).get("tier",99),-float(x.get("adjusted_total",0))))[:10]
    sectors=sorted(data.get("sector_rankings") or [], key=lambda x: float(x.get("avg_change",0)), reverse=True)[:8]
    queries=["A股 今日 收盘 热点 板块", "A股 政策 产业 新闻", "中国 股市 盘后", "美股 盘前 市场", "黄金 原油 美债 美元"]
    news=[]
    for q in queries:
        news.extend(google_news_rss(q)[:8])
    output={
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "source_scan_date": data.get("scan_date"),
        "focus_candidates":[{"code":x.get("code"),"name":x.get("name"),"score":x.get("adjusted_total"),"pool":x.get("pool"),"tier":x.get("recency",{}).get("tier"),"sector":x.get("sector")} for x in focus],
        "top_sectors":sectors,
        "headlines":news[:40],
        "notes":[
            "20:00层只做明日预判，不修改七因子评分。",
            "新闻为自动抓取候选素材，需要次日竞价再次验证。",
        ],
    }
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(output,f,ensure_ascii=False,indent=2)
    print(f"[Evening] generated {OUT}; focus={len(focus)}, headlines={len(news[:40])}")

if __name__=="__main__": main()
