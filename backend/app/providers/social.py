from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

POS_WORDS = (
    "上涨", "大涨", "突破", "利好", "增持", "回购", "超预期", "吸金", "新高",
    "看好", "加仓", "买入", "反弹", "业绩", "增长", "开门红", "抢光",
)
NEG_WORDS = (
    "下跌", "大跌", "破位", "利空", "减持", "抛售", "下滑", "亏损", "风险",
    "看空", "清仓", "卖出", "暴雷", "套牢", "踩雷", "阴跌", "退市",
)


def _client() -> httpx.Client:
    return httpx.Client(timeout=20.0, headers=HEADERS, follow_redirects=True)


def _extract_json_object(text: str, start: int) -> str:
    """从 start 位置提取平衡的 {...} JSON 对象。"""
    if start < 0 or start >= len(text) or text[start] != "{":
        return ""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def _sentiment_of(text: str) -> str:
    p = sum(1 for w in POS_WORDS if w in text)
    n = sum(1 for w in NEG_WORDS if w in text)
    if p > n:
        return "positive"
    if n > p:
        return "negative"
    return "neutral"


def _em_symbol(code: str) -> str:
    code = code.zfill(6)
    return ("SH" if code.startswith(("5", "6", "9")) else "SZ") + code


def fetch_guba_posts(code: str, limit: int = 30) -> list[dict[str, Any]]:
    """东方财富股吧帖子（含标题/互动）。"""
    code = code.zfill(6)
    url = f"https://guba.eastmoney.com/list,{code}.html"
    with _client() as c:
        r = c.get(url, headers={**HEADERS, "Referer": "https://guba.eastmoney.com/"})
        r.raise_for_status()
        text = r.text
    m = re.search(r"var article_list\s*=\s*\{", text)
    if not m:
        return []
    start = m.end() - 1
    raw = _extract_json_object(text, start)
    if not raw:
        return []
    data = json.loads(raw)

    items = []
    for row in (data.get("re") or [])[:limit]:
        title = str(row.get("post_title") or "").strip()
        if not title:
            continue
        pid = row.get("post_id")
        nick = str(row.get("user_nickname") or "股吧用户")
        items.append(
            {
                "id": f"guba-{pid}",
                "platform": "eastmoney_guba",
                "platform_label": "东方财富股吧",
                "title": title,
                "summary": title,
                "author": nick,
                "published_at": str(row.get("post_publish_time") or "")[:19],
                "click": int(row.get("post_click_count") or 0),
                "comment": int(row.get("post_comment_count") or 0),
                "forward": int(row.get("post_forward_count") or 0),
                "sentiment": _sentiment_of(title),
                "url": f"https://guba.eastmoney.com/news,{code},{pid}.html" if pid else url,
            }
        )
    return items


def fetch_sina_news(code: str, limit: int = 15) -> list[dict[str, Any]]:
    """新浪财经个股资讯。"""
    code = code.zfill(6)
    market = "sh" if code.startswith(("5", "6", "9")) else "sz"
    url = (
        "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php"
        f"?symbol={market}{code}&Page=1"
    )
    with _client() as c:
        r = c.get(url, headers={**HEADERS, "Referer": "https://finance.sina.com.cn/"})
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    items: list[dict[str, Any]] = []
    # 结构: datelist 下 date + a
    block = soup.select_one("div.datelist")
    if block:
        texts = list(block.stripped_strings)
        # pairs roughly date then title
        i = 0
        while i < len(texts) - 1 and len(items) < limit:
            maybe_date = texts[i]
            title = texts[i + 1]
            if re.match(r"\d{4}-\d{2}-\d{2}", maybe_date) and len(title) >= 6:
                href = ""
                for a in block.find_all("a", href=True):
                    if a.get_text(strip=True) == title:
                        href = a["href"]
                        break
                items.append(
                    {
                        "id": f"sina-{len(items)}",
                        "platform": "sina",
                        "platform_label": "新浪财经",
                        "title": title,
                        "summary": title,
                        "author": "新浪财经",
                        "published_at": maybe_date,
                        "click": 0,
                        "comment": 0,
                        "forward": 0,
                        "sentiment": _sentiment_of(title),
                        "url": href,
                    }
                )
                i += 2
                continue
            i += 1
    if items:
        return items[:limit]

    # fallback: any news-like anchors
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"]
        if len(title) < 10 or "javascript" in href:
            continue
        if code not in title and "茅台" not in title and "股" not in title:
            # keep general finance links cautiously
            if not any(k in title for k in ("公司", "公告", "业绩", "股价", "融资")):
                continue
        items.append(
            {
                "id": f"sina-{len(items)}",
                "platform": "sina",
                "platform_label": "新浪财经",
                "title": title,
                "summary": title,
                "author": "新浪财经",
                "published_at": "",
                "click": 0,
                "comment": 0,
                "forward": 0,
                "sentiment": _sentiment_of(title),
                "url": href,
            }
        )
        if len(items) >= limit:
            break
    return items[:limit]


def fetch_hot_meta(code: str) -> dict[str, Any]:
    """人气排名、关注指数、综合评分、关联股、热门概念。"""
    import akshare as ak

    code = code.zfill(6)
    sym = _em_symbol(code)
    out: dict[str, Any] = {
        "hot_rank": None,
        "focus_index": None,
        "score": None,
        "related": [],
        "keywords": [],
        "source": "eastmoney",
    }

    try:
        df = ak.stock_hot_rank_detail_em(symbol=sym)
        if df is not None and not df.empty:
            last = df.iloc[-1]
            out["hot_rank"] = int(last.get("排名") or 0) or None
            out["new_fans_ratio"] = float(last.get("新晋粉丝") or 0)
            out["core_fans_ratio"] = float(last.get("铁杆粉丝") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hot rank failed: %s", exc)

    try:
        df = ak.stock_comment_detail_scrd_focus_em(symbol=code)
        if df is not None and not df.empty:
            out["focus_index"] = float(df.iloc[-1].iloc[-1])
    except Exception as exc:  # noqa: BLE001
        logger.warning("focus index failed: %s", exc)

    try:
        df = ak.stock_comment_detail_zhpj_lspf_em(symbol=code)
        if df is not None and not df.empty:
            out["score"] = round(float(df.iloc[-1].iloc[-1]), 2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("zhpj score failed: %s", exc)

    try:
        df = ak.stock_hot_rank_relate_em(symbol=sym)
        if df is not None and not df.empty:
            for _, row in df.head(8).iterrows():
                rel = str(row.get("相关股票代码") or "")
                m = re.search(r"(\d{6})", rel)
                if not m:
                    continue
                out["related"].append(
                    {
                        "code": m.group(1),
                        "symbol": rel,
                        "change_pct": float(row.get("涨跌幅") or 0),
                        "relation": "人气关联",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("related failed: %s", exc)

    try:
        df = ak.stock_hot_keyword_em(symbol=sym)
        if df is not None and not df.empty:
            for _, row in df.head(8).iterrows():
                out["keywords"].append(
                    {
                        "name": str(row.get("概念名称") or ""),
                        "heat": float(row.get("热度") or 0),
                        "board": str(row.get("概念代码") or ""),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("keywords failed: %s", exc)

    return out


def build_social_bundle(code: str) -> dict[str, Any]:
    code = code.zfill(6)
    guba: list[dict[str, Any]] = []
    sina: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        guba = fetch_guba_posts(code)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"guba:{exc}")
        logger.warning("guba failed: %s", exc)

    try:
        sina = fetch_sina_news(code)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"sina:{exc}")
        logger.warning("sina failed: %s", exc)

    try:
        hot = fetch_hot_meta(code)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"hot:{exc}")
        hot = {"related": [], "keywords": []}

    posts = guba + sina
    pos = sum(1 for p in posts if p.get("sentiment") == "positive")
    neg = sum(1 for p in posts if p.get("sentiment") == "negative")
    neu = len(posts) - pos - neg
    # weighted by engagement for guba
    w_pos = w_neg = 0.0
    for p in guba:
        w = 1 + (p.get("click") or 0) / 5000 + (p.get("comment") or 0) / 20
        if p["sentiment"] == "positive":
            w_pos += w
        elif p["sentiment"] == "negative":
            w_neg += w
        else:
            w_pos += 0.3 * w
            w_neg += 0.3 * w
    if w_pos + w_neg > 0:
        mood = 50 + (w_pos - w_neg) / (w_pos + w_neg) * 40
    elif pos + neg > 0:
        mood = 50 + (pos - neg) / (pos + neg) * 35
    else:
        mood = 50.0

    # blend official score / focus if present
    if hot.get("score") is not None:
        mood = 0.55 * mood + 0.45 * float(hot["score"])
    mood = max(0.0, min(100.0, mood))
    if mood >= 65:
        label = "偏多"
    elif mood <= 40:
        label = "偏空"
    else:
        label = "中性"

    return {
        "code": code,
        "platforms": ["东方财富股吧", "新浪财经", "东财人气/评分"],
        "posts": posts[:40],
        "guba_count": len(guba),
        "news_count": len(sina),
        "mood_score": round(mood, 1),
        "mood_label": label,
        "mood_breakdown": {"positive": pos, "negative": neg, "neutral": neu},
        "hot_rank": hot.get("hot_rank"),
        "focus_index": hot.get("focus_index"),
        "community_score": hot.get("score"),
        "related": hot.get("related") or [],
        "keywords": hot.get("keywords") or [],
        "summary": _social_summary(code, mood, label, guba, hot),
        "degraded": len(posts) == 0,
        "errors": errors or None,
        "source": "guba+sina+em_hot",
    }


def _social_summary(code: str, mood: float, label: str, guba: list, hot: dict) -> str:
    rank = hot.get("hot_rank")
    focus = hot.get("focus_index")
    parts = [f"舆情得分 {mood:.0f}（{label}）"]
    if guba:
        parts.append(f"股吧近帖 {len(guba)} 条")
    if rank:
        parts.append(f"人气排名约第 {rank}")
    if focus is not None:
        parts.append(f"关注指数 {focus}")
    rel = hot.get("related") or []
    if rel:
        codes = ",".join(r["code"] for r in rel[:3])
        parts.append(f"关联热股 {codes}")
    return "；".join(parts) + "。"
