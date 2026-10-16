from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.core.demo_data import demo_news
from app.services.market import _normalize_code, get_quote

logger = logging.getLogger(__name__)


def get_news(code: str, limit: int = 20) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"news:{code}:{limit}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    items = demo_news(code)
    degraded = True
    reason = "demo_mode" if settings.demo_mode else "fallback"
    if not settings.demo_mode:
        try:
            live = _live_news(code, limit=limit)
            if live:
                items = live
                degraded = False
                reason = ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("live news failed: %s", exc)
            reason = str(exc)

    quote = get_quote(code)
    payload = {
        "code": code,
        "name": quote.get("name", code),
        "items": items[:limit],
        "degraded": degraded,
        "degrade_reason": reason,
    }
    cache.set(key, payload)
    return payload


def _live_news(code: str, limit: int = 20) -> list[dict[str, Any]]:
    import akshare as ak

    df = ak.stock_news_em(symbol=code)
    if df is None or df.empty:
        return []
    items: list[dict[str, Any]] = []
    for i, r in df.head(limit).iterrows():
        title = str(r.get("新闻标题", r.get("title", "")))
        content = str(r.get("新闻内容", r.get("content", "")))[:180]
        sentiment = "neutral"
        for w in ("增长", "超预期", "签约", "中标", "回购"):
            if w in title or w in content:
                sentiment = "positive"
        for w in ("下滑", "亏损", "调查", "减持", "风险"):
            if w in title or w in content:
                sentiment = "negative"
        items.append(
            {
                "id": f"{code}-{i}",
                "title": title,
                "source": str(r.get("文章来源", "东方财富")),
                "published_at": str(r.get("发布时间", ""))[:19],
                "summary": content,
                "sentiment": sentiment,
                "url": str(r.get("新闻链接", "")),
            }
        )
    return items
