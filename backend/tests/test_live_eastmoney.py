from __future__ import annotations

import os

import pytest

# 实盘集成测试：网络/数据源不可用时跳过，不阻断 CI
os.environ["ASHARE_DEMO_MODE"] = "0"

from app.core.cache import cache
from app.providers import eastmoney as em


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()


def test_live_quote_maotai():
    try:
        q = em.get_quote("600519")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"live quote unavailable: {exc}")
    assert q["name"] == "贵州茅台"
    assert q["price"] > 0
    assert q.get("source") == "eastmoney"
    assert q.get("degraded") is False


def test_live_kline_and_research_pipeline():
    try:
        rows = em.get_kline("600519", limit=60)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"live kline unavailable: {exc}")
    assert len(rows) >= 30
    assert rows[-1]["close"] > 0

    from app.services.research import build_research

    cache.clear()
    r = build_research("600519")
    assert r["quote"]["price"] > 0
    assert r["kline"]["items"]
    assert r["forecast"]["stance"]
    # 允许局部降级，但报价/K线应尽量实盘
    assert r["quote"].get("source") in ("eastmoney", "kline_derived")
