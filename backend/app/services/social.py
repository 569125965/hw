from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.providers import social as social_provider
from app.services.market import _normalize_code

logger = logging.getLogger(__name__)


def get_social(code: str) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"social:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    if settings.demo_mode:
        data = _demo_social(code)
    else:
        try:
            data = social_provider.build_social_bundle(code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("social live failed: %s", exc)
            data = _demo_social(code)
            data["degraded"] = True
            data["degrade_reason"] = str(exc)

    cache.set(key, data)
    return data


def _demo_social(code: str) -> dict[str, Any]:
    return {
        "code": code,
        "platforms": ["演示"],
        "posts": [],
        "guba_count": 0,
        "news_count": 0,
        "mood_score": 50.0,
        "mood_label": "中性",
        "mood_breakdown": {"positive": 0, "negative": 0, "neutral": 0},
        "hot_rank": None,
        "focus_index": None,
        "community_score": None,
        "related": [],
        "keywords": [],
        "summary": "演示模式：未拉取股吧/新闻舆情。",
        "degraded": True,
        "source": "demo",
    }
