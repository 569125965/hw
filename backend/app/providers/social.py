from __future__ import annotations

import json
import logging
import re
from typing import Any

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
    "上涨", "大涨", "涨停", "连板", "突破", "利好", "增持", "回购", "超预期", "吸金",
    "新高", "看好", "加仓", "买入", "反弹", "业绩", "增长", "开门红", "抢光", "龙头",
    "爆款", "热销", "签约", "中标", "量产", "放量上涨",
)
NEG_WORDS = (
    "下跌", "大跌", "破位", "利空", "减持", "抛售", "下滑", "亏损", "风险",
    "看空", "清仓", "卖出", "暴雷", "套牢", "踩雷", "阴跌", "退市",
    "刹车", "争议", "调查", "下架", "断裂", "召回", "翻车", "问询", "处罚",
    "造假", "事故", "维权", "爆仓", "崩盘", "跌停",
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


def heat_score_from_rank(rank: int | None, market_size: int = 5000) -> float | None:
    """东财人气排名 → 0-100 热度分。排名越靠前分越高。"""
    if rank is None or rank <= 0:
        return None
    if rank == 1:
        return 99.0
    if rank <= 3:
        return 96.0 - (rank - 1) * 1.5  # 2→94.5, 3→93
    if rank <= 10:
        return 90.0 - (rank - 4) * 1.2
    if rank <= 50:
        return 78.0 - (rank - 11) * 0.35
    if rank <= 100:
        return 62.0 - (rank - 51) * 0.2
    if rank <= 500:
        return 50.0 - (rank - 101) * 0.03
    # 越靠后越接近冷清
    return max(15.0, 38.0 - (rank / max(market_size, 1)) * 20)


def fetch_em_hot_rank(code: str) -> dict[str, Any]:
    """直连东财人气榜 API（不依赖 akshare）。"""
    code = code.zfill(6)
    sym = _em_symbol(code)
    out: dict[str, Any] = {
        "hot_rank": None,
        "rank_change": None,
        "market_count": None,
        "calc_time": None,
        "source": "emappdata",
    }
    body = {"appId": "appId01", "globalId": "", "srcSecurityCode": sym}
    with _client() as c:
        r = c.post(
            "https://emappdata.eastmoney.com/stockrank/getCurrentLatest",
            json=body,
            headers={**HEADERS, "Content-Type": "application/json", "Referer": "https://guba.eastmoney.com/"},
        )
        r.raise_for_status()
        data = r.json().get("data") or {}
        if data.get("rank"):
            out["hot_rank"] = int(data["rank"])
            out["rank_change"] = data.get("rankChange")
            out["market_count"] = int(data.get("marketAllCount") or 0) or None
            out["calc_time"] = data.get("calcTime")
            return out

        # fallback: scan top list
        r2 = c.post(
            "https://emappdata.eastmoney.com/stockrank/getAllCurrentList",
            json={"appId": "appId01", "globalId": "", "pageNo": 1, "pageSize": 100},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        r2.raise_for_status()
        for row in r2.json().get("data") or []:
            if str(row.get("sc") or "").upper() == sym:
                out["hot_rank"] = int(row.get("rk") or 0) or None
                out["rank_change"] = row.get("rc")
                return out
    return out


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
    block = soup.select_one("div.datelist")
    if block:
        texts = list(block.stripped_strings)
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

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"]
        if len(title) < 10 or "javascript" in href:
            continue
        if code not in title and "茅台" not in title and "股" not in title:
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
    code = code.zfill(6)
    sym = _em_symbol(code)
    out: dict[str, Any] = {
        "hot_rank": None,
        "focus_index": None,
        "score": None,
        "related": [],
        "keywords": [],
        "source": "eastmoney",
        "market_count": None,
        "rank_change": None,
        "calc_time": None,
    }

    # 1) 直连东财人气 API（主路径）
    try:
        em = fetch_em_hot_rank(code)
        out["hot_rank"] = em.get("hot_rank")
        out["rank_change"] = em.get("rank_change")
        out["market_count"] = em.get("market_count")
        out["calc_time"] = em.get("calc_time")
        out["source"] = em.get("source") or out["source"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("em hot rank failed: %s", exc)

    # 2) akshare 补充 focus / 评分 / 关联 / 关键词；排名作兜底
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        logger.warning("akshare import failed: %s", exc)
        return out

    if out["hot_rank"] is None:
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


def _engagement_heat(guba: list[dict[str, Any]], news_count: int) -> float:
    """股吧互动 + 资讯量 → 热度代理分。"""
    if not guba and news_count <= 0:
        return 40.0
    clicks = sum(int(p.get("click") or 0) for p in guba)
    comments = sum(int(p.get("comment") or 0) for p in guba)
    # 江淮这类热帖单帖 5万+ 阅，总和常 >20万
    click_score = min(40.0, clicks / 8000.0)
    comment_score = min(25.0, comments / 40.0)
    news_score = min(20.0, news_count * 1.2)
    post_score = min(15.0, len(guba) * 0.5)
    return max(20.0, min(95.0, 25.0 + click_score + comment_score + news_score + post_score))


def _polarity_score(posts: list[dict[str, Any]], guba: list[dict[str, Any]]) -> float:
    pos = sum(1 for p in posts if p.get("sentiment") == "positive")
    neg = sum(1 for p in posts if p.get("sentiment") == "negative")
    w_pos = w_neg = 0.0
    for p in guba:
        w = 1 + (p.get("click") or 0) / 5000 + (p.get("comment") or 0) / 20
        if p["sentiment"] == "positive":
            w_pos += w
        elif p["sentiment"] == "negative":
            w_neg += w
        else:
            # 中性帖不拉向 50/50，只给极弱权重，避免热帖被稀释成「中性」
            w_pos += 0.08 * w
            w_neg += 0.08 * w
    if w_pos + w_neg > 0.5:
        return 50 + (w_pos - w_neg) / (w_pos + w_neg) * 40
    if pos + neg > 0:
        return 50 + (pos - neg) / (pos + neg) * 35
    return 50.0


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

    polarity = _polarity_score(posts, guba)
    engage = _engagement_heat(guba, len(sina))
    rank_heat = heat_score_from_rank(hot.get("hot_rank"), hot.get("market_count") or 5000)
    focus = hot.get("focus_index")
    community = hot.get("score")

    # 人气热度：排名优先，其次关注指数 / 互动
    heat_parts: list[tuple[float, float]] = []
    if rank_heat is not None:
        heat_parts.append((0.55, rank_heat))
    if focus is not None:
        heat_parts.append((0.25, float(focus)))
    heat_parts.append((0.20 if rank_heat is not None else 0.45, engage))
    if community is not None and rank_heat is None:
        heat_parts.append((0.25, float(community)))
    wsum = sum(w for w, _ in heat_parts) or 1.0
    heat = sum(w * v for w, v in heat_parts) / wsum
    heat = max(0.0, min(100.0, heat))

    # 综合舆情：人气热度为主（反映「铺天盖地」），极性为辅（涨跌方向）
    if community is not None:
        mood = 0.50 * heat + 0.30 * polarity + 0.20 * float(community)
    else:
        mood = 0.55 * heat + 0.45 * polarity
    mood = max(0.0, min(100.0, mood))

    if heat >= 85 or (hot.get("hot_rank") and hot["hot_rank"] <= 10):
        label = "高热" if polarity >= 45 else "高热偏空"
    elif mood >= 65:
        label = "偏多"
    elif mood <= 40:
        label = "偏空"
    else:
        label = "中性"

    heat_label = (
        "爆棚" if heat >= 90 else
        "极高" if heat >= 80 else
        "较高" if heat >= 65 else
        "一般" if heat >= 45 else
        "偏冷"
    )

    return {
        "code": code,
        "platforms": ["东方财富股吧", "新浪财经", "东财人气榜"],
        "posts": posts[:40],
        "guba_count": len(guba),
        "news_count": len(sina),
        "mood_score": round(mood, 1),
        "mood_label": label,
        "polarity_score": round(polarity, 1),
        "heat_score": round(heat, 1),
        "heat_label": heat_label,
        "mood_breakdown": {"positive": pos, "negative": neg, "neutral": neu},
        "hot_rank": hot.get("hot_rank"),
        "rank_change": hot.get("rank_change"),
        "market_count": hot.get("market_count"),
        "focus_index": hot.get("focus_index"),
        "community_score": hot.get("score"),
        "related": hot.get("related") or [],
        "keywords": hot.get("keywords") or [],
        "summary": _social_summary(code, mood, label, heat, heat_label, guba, hot, polarity),
        "degraded": len(posts) == 0 and hot.get("hot_rank") is None,
        "errors": errors or None,
        "source": "guba+sina+em_hot",
    }


def _social_summary(
    code: str,
    mood: float,
    label: str,
    heat: float,
    heat_label: str,
    guba: list,
    hot: dict,
    polarity: float,
) -> str:
    rank = hot.get("hot_rank")
    focus = hot.get("focus_index")
    market = hot.get("market_count")
    parts: list[str] = []
    if rank:
        total = f"/{market}" if market else ""
        parts.append(f"东财人气榜第 {rank}{total}（关注度{heat_label}）")
    else:
        parts.append(f"市场关注度{heat_label}（热度 {heat:.0f}）")
    parts.append(f"舆情综合 {mood:.0f}（{label}）")
    parts.append(f"标题倾向 {polarity:.0f}")
    if guba:
        clicks = sum(int(p.get("click") or 0) for p in guba)
        parts.append(f"股吧近帖 {len(guba)} 条·阅读约 {clicks}")
    if focus is not None:
        parts.append(f"关注指数 {focus}")
    rel = hot.get("related") or []
    if rel:
        codes = ",".join(r["code"] for r in rel[:3])
        parts.append(f"关联热股 {codes}")
    return "；".join(parts) + "。"
