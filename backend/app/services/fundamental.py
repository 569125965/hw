from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache
from app.core.config import settings
from app.core.demo_data import demo_fundamental
from app.services.market import _normalize_code, get_quote

logger = logging.getLogger(__name__)


def get_fundamental(code: str) -> dict[str, Any]:
    code = _normalize_code(code)
    key = f"fund:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    data = demo_fundamental(code)
    if not settings.demo_mode:
        try:
            live = _live_fundamental(code)
            if live:
                data = live
        except Exception as exc:  # noqa: BLE001
            logger.warning("live fundamental failed: %s", exc)
            data["degraded"] = True
            data["degrade_reason"] = str(exc)
    else:
        data["degrade_reason"] = "demo_mode"

    # enrich peer quotes lightly from demo/live quote when possible
    peers = []
    for p in data.get("peers", []):
        try:
            q = get_quote(p["code"])
            peers.append(
                {
                    **p,
                    "price": q.get("price"),
                    "change_pct": q.get("change_pct", p.get("change_pct")),
                }
            )
        except Exception:  # noqa: BLE001
            peers.append(p)
    data["peers"] = peers
    cache.set(key, data)
    return data


def _live_fundamental(code: str) -> dict[str, Any] | None:
    import akshare as ak

    quote = get_quote(code)
    name = quote.get("name", code)
    industry = "未知"
    try:
        info = ak.stock_individual_info_em(symbol=code)
        mapping = {str(r["item"]): str(r["value"]) for _, r in info.iterrows()}
        industry = mapping.get("行业", industry)
    except Exception:  # noqa: BLE001
        pass

    concepts: list[str] = []
    try:
        board = ak.stock_board_concept_name_em()
        # best-effort sample concepts
        concepts = board["板块名称"].head(3).tolist()
    except Exception:  # noqa: BLE001
        concepts = ["A股", industry]

    return {
        "code": code,
        "name": name,
        "industry": industry,
        "concepts": concepts[:6],
        "products": [
            {"name": "主营业务", "share": 0.7, "desc": f"以{industry}相关业务为主"},
            {"name": "其他业务", "share": 0.3, "desc": "补充收入"},
        ],
        "business_summary": f"{name} 所属行业为{industry}，请结合财报与公告做进一步验证。",
        "peers": [],
        "degraded": False,
    }
