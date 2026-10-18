from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.providers import macro as macro_provider

logger = logging.getLogger(__name__)


def get_macro() -> dict[str, Any]:
    key = "macro:drivers"
    hit = cache.get(key)
    if hit is not None:
        return hit

    if settings.demo_mode:
        data = {
            "items": [],
            "bucket_counts": {"fed": 0, "geopolitics": 0, "china_policy": 0, "risk": 0},
            "risk_score": 50,
            "regime": "中性震荡",
            "summary": "演示模式：未拉取宏观驱动。",
            "degraded": True,
            "source": "demo",
        }
    else:
        try:
            data = macro_provider.build_macro_bundle(limit=40)
        except Exception as exc:  # noqa: BLE001
            logger.warning("macro failed: %s", exc)
            data = {
                "items": [],
                "bucket_counts": {},
                "risk_score": 50,
                "regime": "未知",
                "summary": f"宏观采集失败：{exc}",
                "degraded": True,
                "source": "error",
            }

    cache.set(key, data)
    return data
