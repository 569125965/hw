from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.providers.social import HEADERS, _sentiment_of

logger = logging.getLogger(__name__)

# 驱动因素关键词桶
BUCKETS: dict[str, tuple[str, ...]] = {
    "fed": ("美联储", "降息", "加息", "点阵图", "鲍威尔", "非农", "CPI", "PCE", "缩表", "利率决议", "FOMC"),
    "geopolitics": ("地缘", "战争", "冲突", "制裁", "关税", "中东", "台海", "俄乌", "以伊", "朝核", "南海"),
    "china_policy": ("降准", "降息", "央行", "证监会", "国常会", "刺激", "稳增长", "专项债", "IPO", "印花税"),
    "risk": ("避险", "恐慌", "崩盘", "熔断", "暴跌", "黑天鹅", "流动性", "违约"),
}


def _client() -> httpx.Client:
    return httpx.Client(timeout=20.0, headers=HEADERS, follow_redirects=True)


def _classify(title: str) -> list[str]:
    hits = []
    for bucket, words in BUCKETS.items():
        if any(w in title for w in words):
            hits.append(bucket)
    return hits or ["general"]


def fetch_eastmoney_macro_news(limit: int = 30) -> list[dict[str, Any]]:
    """东财财经要闻/全球搜索（美联储、地缘等）。"""
    queries = ["美联储", "地缘政治", "降息", "战争", "关税"]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    with _client() as c:
        for q in queries:
            try:
                url = (
                    "https://search-api-web.eastmoney.com/search/jsonp"
                    f"?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{quote(q)}%22"
                    "%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22"
                    f"%2C%22clientType%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A{min(limit, 10)}%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D"
                )
                r = c.get(url, headers={**HEADERS, "Referer": "https://so.eastmoney.com/"})
                r.raise_for_status()
                text = r.text
                m = re.search(r"jQuery\((.*)\)\s*$", text, re.S)
                if not m:
                    continue
                import json

                data = json.loads(m.group(1))
                arts = (((data.get("result") or {}).get("cmsArticleWebOld") or []))[:10]
                for i, a in enumerate(arts):
                    title = str(a.get("title") or "").strip()
                    if not title or title in seen:
                        continue
                    seen.add(title)
                    buckets = _classify(title + str(a.get("content") or ""))
                    items.append(
                        {
                            "id": f"macro-em-{q}-{i}",
                            "title": title,
                            "summary": str(a.get("content") or title)[:180],
                            "source": "东方财富",
                            "published_at": str(a.get("date") or a.get("showTime") or "")[:19],
                            "url": a.get("url") or "",
                            "buckets": buckets,
                            "sentiment": _sentiment_of(title),
                            "query": q,
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("macro em search %s failed: %s", q, exc)
    return items[:limit]


def fetch_sina_finance_roll(limit: int = 20) -> list[dict[str, Any]]:
    """新浪财经滚动要闻（宏观兜底）。"""
    url = "https://finance.sina.com.cn/roll/index.d.html?cid=56592&page=1"
    items: list[dict[str, Any]] = []
    try:
        with _client() as c:
            r = c.get(url, headers={**HEADERS, "Referer": "https://finance.sina.com.cn/"})
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("ul.list_009 li a, .list_009 a, a")[:80]:
            title = a.get_text(strip=True)
            href = a.get("href") or ""
            if len(title) < 8 or "javascript" in href:
                continue
            buckets = _classify(title)
            if buckets == ["general"] and not any(w in title for w in ("美", "联储", "战争", "降息", "地缘", "央行")):
                continue
            items.append(
                {
                    "id": f"macro-sina-{len(items)}",
                    "title": title,
                    "summary": title,
                    "source": "新浪财经",
                    "published_at": "",
                    "url": href,
                    "buckets": buckets,
                    "sentiment": _sentiment_of(title),
                    "query": "roll",
                }
            )
            if len(items) >= limit:
                break
    except Exception as exc:  # noqa: BLE001
        logger.warning("sina macro failed: %s", exc)
    return items


def build_macro_bundle(limit: int = 40) -> dict[str, Any]:
    items = fetch_eastmoney_macro_news(limit=limit)
    if len(items) < 8:
        items.extend(fetch_sina_finance_roll(limit=20))
    # dedupe by title
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for it in items:
        t = it["title"]
        if t in seen:
            continue
        seen.add(t)
        uniq.append(it)

    counts = {k: 0 for k in BUCKETS}
    risk_hits = 0
    for it in uniq:
        for b in it.get("buckets") or []:
            if b in counts:
                counts[b] += 1
            if b in ("geopolitics", "risk"):
                risk_hits += 1

    # 宏观风险分：越高越避险
    risk_score = min(95.0, 35 + risk_hits * 6 + counts["fed"] * 2)
    if counts["china_policy"] >= 3 and risk_hits <= 2:
        risk_score = max(25.0, risk_score - 12)

    if risk_score >= 70:
        regime = "避险"
    elif risk_score <= 40:
        regime = "风险偏好"
    else:
        regime = "中性震荡"

    summary = (
        f"宏观驱动：美联储相关 {counts['fed']} 条，地缘/战争 {counts['geopolitics']} 条，"
        f"国内政策 {counts['china_policy']} 条；当前偏「{regime}」（风险分 {risk_score:.0f}）。"
    )
    return {
        "items": uniq[:limit],
        "bucket_counts": counts,
        "risk_score": round(risk_score, 1),
        "regime": regime,
        "summary": summary,
        "degraded": len(uniq) == 0,
        "source": "eastmoney+sina",
    }
