from __future__ import annotations

import os

os.environ["ASHARE_DEMO_MODE"] = "1"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search():
    r = client.get("/api/v1/stocks/search", params={"q": "茅台"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["code"] == "600519" for i in items)


def test_quote_and_kline():
    q = client.get("/api/v1/stocks/600519/quote")
    assert q.status_code == 200
    body = q.json()
    assert body["code"] == "600519"
    assert "price" in body

    k = client.get("/api/v1/stocks/600519/kline", params={"period": "day", "limit": 60})
    assert k.status_code == 200
    items = k.json()["items"]
    assert len(items) >= 30
    assert "ma5" in items[-1]


def test_research_bundle():
    r = client.get("/api/v1/stocks/600519/research")
    assert r.status_code == 200
    data = r.json()
    assert data["quote"]["name"]
    assert data["sentiment"]["score"] >= 0
    assert data["forecast"]["stance"]
    assert data["forecast"]["actions"]
    assert "disclaimer" in data["forecast"]


def test_name_normalize():
    r = client.get("/api/v1/stocks/贵州茅台/quote")
    assert r.status_code == 200
    assert r.json()["code"] == "600519"


def test_signals_paired_by_cycle():
    r = client.get("/api/v1/stocks/600519/signals", params={"limit": 180})
    assert r.status_code == 200
    signals = r.json()["signals"]
    assert isinstance(signals, list)
    assert len(signals) >= 2
    assert any(s["cycle"] == "short" for s in signals)

    for cycle in ("short", "medium"):
        items = [s for s in signals if s["cycle"] == cycle]
        by_pair: dict[str, list] = {}
        for s in items:
            by_pair.setdefault(s["pair_id"], []).append(s)
        for pair_id, pair in by_pair.items():
            sides = sorted(x["side"] for x in pair)
            assert sides == ["buy", "sell"], pair_id
            buy = next(x for x in pair if x["side"] == "buy")
            sell = next(x for x in pair if x["side"] == "sell")
            assert sell["index"] >= buy["index"]

    k = client.get("/api/v1/stocks/600519/kline", params={"limit": 180})
    assert "signals" in k.json()
    assert len(k.json()["signals"]) >= 2
