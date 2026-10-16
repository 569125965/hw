from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.core.demo_data import demo_fundamental
from app.providers import eastmoney as em
from app.services.market import _normalize_code

logger = logging.getLogger(__name__)


def get_fundamental(code: str) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"fund:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    data: dict[str, Any] | None = None
    if not settings.demo_mode:
        try:
            data = em.get_fundamental(code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live fundamental failed: %s", exc)

    if data is None:
        data = demo_fundamental(code)
        data["degraded"] = True
        data["degrade_reason"] = "demo_fallback"
        data["source"] = "demo"

    cache.set(key, data)
    return data
