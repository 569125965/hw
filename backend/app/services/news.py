from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.core.demo_data import demo_news
from app.providers import eastmoney as em
from app.services.market import _normalize_code, get_quote

logger = logging.getLogger(__name__)


def get_news(code: str, limit: int = 20) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"news:{code}:{limit}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    items: list[dict[str, Any]] = []
    degraded = False
    reason = ""
    if not settings.demo_mode:
        try:
            items = em.get_news(code, limit=limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live news failed: %s", exc)
            reason = str(exc)

    if not items:
        items = demo_news(code)
        degraded = True
        reason = reason or "demo_fallback"

    quote = get_quote(code)
    payload = {
        "code": code,
        "name": quote.get("name", code),
        "items": items[:limit],
        "degraded": degraded,
        "degrade_reason": reason,
        "source": "eastmoney" if not degraded else "demo",
    }
    cache.set(key, payload)
    return payload
