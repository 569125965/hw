from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any


DEMO_STOCKS: list[dict[str, str]] = [
    {"code": "600519", "name": "贵州茅台", "market": "SH"},
    {"code": "000858", "name": "五粮液", "market": "SZ"},
    {"code": "300750", "name": "宁德时代", "market": "SZ"},
    {"code": "002594", "name": "比亚迪", "market": "SZ"},
    {"code": "600036", "name": "招商银行", "market": "SH"},
    {"code": "601318", "name": "中国平安", "market": "SH"},
    {"code": "000001", "name": "平安银行", "market": "SZ"},
    {"code": "510300", "name": "沪深300ETF", "market": "SH"},
    {"code": "688981", "name": "中芯国际", "market": "SH"},
    {"code": "002415", "name": "海康威视", "market": "SZ"},
]


FUNDAMENTAL_MAP: dict[str, dict[str, Any]] = {
    "600519": {
        "industry": "白酒",
        "concepts": ["消费龙头", "高股息", "品牌护城河"],
        "products": [
            {"name": "飞天茅台", "share": 0.62, "desc": "核心大单品，渠道控货稳价"},
            {"name": "系列酒", "share": 0.28, "desc": "腰部放量，承接商务与宴席"},
            {"name": "其他", "share": 0.10, "desc": "文创与定制等"},
        ],
        "business_summary": "高端白酒龙头，品牌与渠道壁垒深厚，盈利能力行业领先。",
        "peers": [
            {"code": "000858", "name": "五粮液", "change_pct": 1.2},
            {"code": "000568", "name": "泸州老窖", "change_pct": -0.4},
            {"code": "600809", "name": "山西汾酒", "change_pct": 0.8},
        ],
    },
    "300750": {
        "industry": "电池",
        "concepts": ["新能源", "储能", "锂电龙头"],
        "products": [
            {"name": "动力电池", "share": 0.72, "desc": "全球装机领先"},
            {"name": "储能电池", "share": 0.20, "desc": "增速最快业务"},
            {"name": "其他", "share": 0.08, "desc": "材料与回收"},
        ],
        "business_summary": "全球动力与储能电池龙头，周期与成长属性并存。",
        "peers": [
            {"code": "002594", "name": "比亚迪", "change_pct": 2.1},
            {"code": "300014", "name": "亿纬锂能", "change_pct": -1.3},
            {"code": "002460", "name": "赣锋锂业", "change_pct": 0.5},
        ],
    },
}


def _stock_meta(code: str) -> dict[str, str]:
    for s in DEMO_STOCKS:
        if s["code"] == code:
            return s
    return {"code": code, "name": f"演示股票{code}", "market": "SH" if code.startswith("6") else "SZ"}


def demo_search(q: str) -> list[dict[str, str]]:
    q = (q or "").strip().lower()
    if not q:
        return DEMO_STOCKS[:8]
    return [
        s
        for s in DEMO_STOCKS
        if q in s["code"].lower() or q in s["name"].lower()
    ][:20]


def _seed_price(code: str) -> float:
    base = sum(ord(c) for c in code) % 200
    return 20 + base + (int(code[-2:]) % 17) * 0.7


def demo_kline(code: str, days: int = 180) -> list[dict[str, Any]]:
    price = _seed_price(code)
    rows: list[dict[str, Any]] = []
    vol_base = 800000 + (int(code) % 50) * 10000
    start = date.today() - timedelta(days=days + 10)
    i = 0
    d = start
    while len(rows) < days:
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        wave = math.sin(i / 9.0) * 0.018 + math.cos(i / 23.0) * 0.01
        drift = 0.0004 if i % 17 != 0 else -0.012
        open_p = price * (1 + drift * 0.3)
        close_p = price * (1 + wave + drift)
        high_p = max(open_p, close_p) * (1 + abs(wave) * 0.4 + 0.003)
        low_p = min(open_p, close_p) * (1 - abs(wave) * 0.4 - 0.003)
        vol = int(vol_base * (1 + abs(wave) * 3 + (0.4 if close_p > open_p else -0.1)))
        amount = vol * (open_p + close_p) / 2
        rows.append(
            {
                "date": d.isoformat(),
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": vol,
                "amount": round(amount, 2),
            }
        )
        price = close_p
        i += 1
    return rows


def demo_quote(code: str) -> dict[str, Any]:
    kl = demo_kline(code, 30)
    last = kl[-1]
    prev = kl[-2]
    change = last["close"] - prev["close"]
    change_pct = change / prev["close"] * 100
    meta = _stock_meta(code)
    return {
        "code": code,
        "name": meta["name"],
        "market": meta["market"],
        "price": last["close"],
        "open": last["open"],
        "high": last["high"],
        "low": last["low"],
        "pre_close": prev["close"],
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "volume": last["volume"],
        "amount": last["amount"],
        "turnover_rate": round(1.2 + abs(change_pct) * 0.35, 2),
        "amplitude": round((last["high"] - last["low"]) / prev["close"] * 100, 2),
        "volume_ratio": round(0.85 + abs(change_pct) * 0.15, 2),
        "pe_ttm": round(18 + (int(code[-3:]) % 40), 1),
        "pb": round(2.1 + (int(code[-2:]) % 10) * 0.3, 2),
        "total_mv": round(last["close"] * (80 + int(code[-3:]) % 400) * 1e8, 2),
        "as_of": last["date"],
        "degraded": True,
    }


def demo_fundamental(code: str) -> dict[str, Any]:
    meta = _stock_meta(code)
    base = FUNDAMENTAL_MAP.get(
        code,
        {
            "industry": "综合",
            "concepts": ["A股样本", "研究演示"],
            "products": [
                {"name": "主营产品A", "share": 0.55, "desc": "核心收入来源"},
                {"name": "主营产品B", "share": 0.30, "desc": "成长业务"},
                {"name": "其他", "share": 0.15, "desc": "补充业务"},
            ],
            "business_summary": f"{meta['name']} 业务结构稳健，细分赛道具备一定竞争力。",
            "peers": [
                {"code": "600036", "name": "招商银行", "change_pct": 0.3},
                {"code": "601318", "name": "中国平安", "change_pct": -0.2},
            ],
        },
    )
    return {
        "code": code,
        "name": meta["name"],
        **base,
        "degraded": True,
    }


def demo_news(code: str) -> list[dict[str, Any]]:
    meta = _stock_meta(code)
    name = meta["name"]
    today = date.today()
    return [
        {
            "id": f"{code}-n1",
            "title": f"{name}：近期经营节奏平稳，渠道反馈积极",
            "source": "研盘资讯",
            "published_at": today.isoformat(),
            "summary": "公司维持稳健经营策略，核心产品动销符合季节性规律。",
            "sentiment": "positive",
            "url": "",
        },
        {
            "id": f"{code}-n2",
            "title": f"行业观察：{name}所属赛道政策与需求边际变化",
            "source": "行业速递",
            "published_at": (today - timedelta(days=2)).isoformat(),
            "summary": "板块内部出现分化，龙头相对抗跌，关注库存与价格信号。",
            "sentiment": "neutral",
            "url": "",
        },
        {
            "id": f"{code}-n3",
            "title": f"{name}股东增减持与机构持仓动态跟踪",
            "source": "市场提示",
            "published_at": (today - timedelta(days=5)).isoformat(),
            "summary": "近阶段未见极端增减持，机构配置保持相对稳定。",
            "sentiment": "neutral",
            "url": "",
        },
        {
            "id": f"{code}-n4",
            "title": "宏观流动性与风险偏好对高估值资产的影响",
            "source": "宏观简评",
            "published_at": (today - timedelta(days=7)).isoformat(),
            "summary": "利率与风险偏好波动可能放大板块弹性，需控制仓位节奏。",
            "sentiment": "negative",
            "url": "",
        },
    ]
