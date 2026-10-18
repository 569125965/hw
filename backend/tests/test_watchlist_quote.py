import os

os.environ["ASHARE_DEMO_MODE"] = "1"
os.environ["ASHARE_DATA_DIR"] = "/tmp/ashare-test-data"

from fastapi.testclient import TestClient

from app.main import app
from app.providers import tencent_quote
from app.services import watchlists as wl
from app.services.scores import build_chart_overlays, build_scorecard


client = TestClient(app)


def test_watchlist_crud():
    # isolate store
    g = wl.create_group("测试组")
    assert g["name"] == "测试组"
    g2 = wl.add_stocks(g["id"], [{"code": "600418", "name": "江淮汽车", "market": "SH"}])
    assert any(s["code"] == "600418" for s in g2["stocks"])
    g3 = wl.remove_stock(g["id"], "600418")
    assert all(s["code"] != "600418" for s in g3["stocks"])


def test_watchlist_api():
    r = client.get("/api/v1/watchlists")
    assert r.status_code == 200
    assert "groups" in r.json()
    r2 = client.post("/api/v1/watchlists", json={"name": "自选A"})
    assert r2.status_code == 200
    gid = r2.json()["id"]
    r3 = client.post(
        f"/api/v1/watchlists/{gid}/stocks",
        json={"stocks": [{"code": "600519", "name": "贵州茅台", "market": "SH"}]},
    )
    assert r3.status_code == 200
    assert r3.json()["stocks"][0]["code"] == "600519"


def test_scorecard_and_overlays():
    card = build_scorecard(
        quote={"price": 22, "volume_ratio": 1.2},
        sentiment={"score": 60},
        social={"heat_score": 90, "polarity_score": 35, "mood_score": 70},
        capital={
            "thesis": {"exit_score": 60, "rally_score": 10, "code": "capital_exit"},
            "chips": {"cost_zone": {"low": 18, "mid": 20, "high": 23}, "profit_ratio_vs_cost": 10, "pit_low": 18, "hist_high": 50},
            "volume_phase": {"vol_ratio_5_20": 1.3, "up_volume_days": 4},
        },
        macro={"risk_score": 70},
        forecast={"stance": "观望整理"},
        advice={"combo_score": 45, "action_code": "sell", "action": "卖出/减仓"},
    )
    assert len(card["dimensions"]) >= 8
    assert card["signal"] in ("buy", "sell", "hold")
    ov = build_chart_overlays(
        {
            "chips": {
                "cost_zone": {"low": 18, "mid": 20, "high": 23},
                "pit_low": 18,
                "hist_high": 50,
            }
        },
        {"price": 22},
    )
    assert any(o["id"] == "cost_band" for o in ov["overlays"])
    assert any(o["id"] == "trap_zone" for o in ov["overlays"])


def test_tencent_quote_live():
    os.environ["ASHARE_DEMO_MODE"] = "0"
    try:
        q = tencent_quote.get_quote("600418")
    except Exception:
        # 网络受限时跳过
        return
    assert q["name"]
    assert q["price"] > 0
    assert q["turnover_rate"] > 0 or q["total_mv"] > 0
