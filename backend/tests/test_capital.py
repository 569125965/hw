from app.services.capital import analyze_capital, _judge_thesis


def _fake_kline_pit_then_rally():
    items = []
    # decline to pit ~18
    price = 45.0
    for i in range(80):
        price = max(18.0, price - 0.35)
        items.append(
            {
                "date": f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1_000_000 + i * 1000,
                "amount": price * (1_000_000 + i * 1000),
            }
        )
    # accumulate around 20
    for i in range(40):
        p = 19.5 + (i % 5) * 0.3
        items.append(
            {
                "date": f"2025-06-{(i % 28) + 1:02d}",
                "open": p,
                "high": p * 1.02,
                "low": p * 0.98,
                "close": p,
                "volume": 5_000_000,
                "amount": p * 5_000_000,
            }
        )
    # rally with volume
    p = 22.0
    for i in range(15):
        p *= 1.03
        items.append(
            {
                "date": f"2025-08-{(i % 28) + 1:02d}",
                "open": p * 0.99,
                "high": p * 1.02,
                "low": p * 0.98,
                "close": p,
                "volume": 8_000_000,
                "amount": p * 8_000_000,
            }
        )
    return items


def test_chip_cost_near_pit_zone():
    kline = {"items": _fake_kline_pit_then_rally()}
    quote = {"code": "600418", "name": "江淮汽车", "price": float(kline["items"][-1]["close"])}
    news = {
        "items": [
            {"title": "尊界V800交付在即", "published_at": "2025-08-01", "summary": ""},
            {"title": "三部门调查刹车争议", "published_at": "2025-08-10", "summary": "刹车门"},
        ]
    }
    social = {"heat_score": 93, "polarity_score": 36, "hot_rank": 3, "posts": []}
    out = analyze_capital("600418", quote=quote, kline=kline, news=news, social=social)
    assert out["chips"]["pit_low"] is not None
    assert out["chips"]["cost_zone"]["mid"] < 30
    assert any(e["type"] == "scandal" for e in out["events"])
    assert out["thesis"]["exit_score"] >= 50
    assert out["thesis"]["code"] in ("capital_exit", "plan_disrupted_watch_exit")


def test_judge_exit_on_heat_scandal():
    thesis = _judge_thesis(
        price=28,
        chips={"cost_zone": {"mid": 20}, "profit_ratio_vs_cost": 40, "placement_hint": None, "pit_low": 18},
        events=[{"type": "scandal", "title": "刹车调查", "label": "负面"}],
        volume_phase={"label": "连续放量拉升"},
        money={"available": True, "main_net_5d": -1e8, "distribution_up_days": 4, "note": "流出"},
        social={"heat_score": 94, "polarity_score": 35, "hot_rank": 3},
    )
    assert thesis["exit_score"] > thesis["rally_score"]
    assert "出逃" in thesis["label"] or "出货" in thesis["label"]
