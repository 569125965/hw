from __future__ import annotations

from typing import Any

import numpy as np

from app.services.indicators import add_indicators, kline_to_df
from app.services.market import get_kline, get_quote
from app.services.sentiment import get_sentiment


def get_forecast(
    code: str,
    *,
    quote: dict[str, Any] | None = None,
    kline: dict[str, Any] | None = None,
    sentiment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quote = quote or get_quote(code)
    kline = kline or get_kline(code, period="day", limit=180)
    sentiment = sentiment or get_sentiment(code, quote=quote, kline=kline)
    df = add_indicators(kline_to_df(kline["items"]))
    price = float(quote["price"])

    if df.empty:
        return {
            "code": code,
            "name": quote.get("name", code),
            "stance": "观望",
            "horizon": "1-4周",
            "summary": "数据不足，建议观望。",
            "actions": ["等待更多有效行情数据"],
            "levels": {},
            "path": [],
            "scenarios": [],
            "confidence": 0.3,
            "disclaimer": _disclaimer(),
        }

    closes = df["close"].astype(float)
    returns = closes.pct_change().dropna()
    vol = float(returns.tail(20).std()) if len(returns) >= 20 else 0.02
    ma20 = float(df["ma20"].dropna().iloc[-1]) if df["ma20"].notna().any() else price
    ma60 = float(df["ma60"].dropna().iloc[-1]) if df["ma60"].notna().any() else price
    rsi = float(df["rsi"].dropna().iloc[-1]) if df["rsi"].notna().any() else 50.0
    boll_up = float(df["boll_up"].dropna().iloc[-1]) if df["boll_up"].notna().any() else price * 1.05
    boll_dn = float(df["boll_dn"].dropna().iloc[-1]) if df["boll_dn"].notna().any() else price * 0.95

    score = float(sentiment["score"])
    trend_up = price > ma20 > ma60
    trend_down = price < ma20 < ma60

    if score >= 65 and trend_up and rsi < 75:
        stance = "逢低关注"
        bias = 0.012
    elif score <= 35 and (trend_down or rsi > 70):
        stance = "谨慎减仓"
        bias = -0.015
    elif rsi > 78:
        stance = "高位防守"
        bias = -0.01
    elif rsi < 28:
        stance = "超卖反弹关注"
        bias = 0.008
    else:
        stance = "观望整理"
        bias = 0.0

    horizons = [5, 10, 20]
    path = []
    for h in horizons:
        expected = price * (1 + bias * (h / 5) + np.clip((score - 50) / 5000, -0.01, 0.01))
        band = price * vol * np.sqrt(h) * 1.65
        path.append(
            {
                "days": h,
                "expected": round(float(expected), 2),
                "low": round(float(expected - band), 2),
                "high": round(float(expected + band), 2),
            }
        )

    support = round(min(boll_dn, ma20 * 0.98, price * (1 - 2 * vol)), 2)
    resist = round(max(boll_up, ma20 * 1.02, price * (1 + 2 * vol)), 2)
    actions = _actions(stance, support, resist, score)
    summary = (
        f"结合盘面、均线结构与情绪分（{score:.0f}），当前思路偏「{stance}」。"
        f"关键支撑约 {support}，压力约 {resist}；"
        f"未来1-4周中枢看向 {path[1]['expected']} 附近（区间 {path[1]['low']}-{path[1]['high']}）。"
    )

    scenarios = [
        {
            "name": "基准",
            "probability": 0.5,
            "desc": f"围绕 {ma20:.2f}/{ma60:.2f} 均线带震荡，等待方向选择。",
        },
        {
            "name": "偏多",
            "probability": 0.25 if score < 60 else 0.35,
            "desc": f"放量站稳压力位 {resist}，情绪与资金共振上行。",
        },
        {
            "name": "偏空",
            "probability": 0.25 if score > 40 else 0.35,
            "desc": f"跌破支撑 {support} 且量能放大，则转入更弱结构。",
        },
    ]

    return {
        "code": code,
        "name": quote.get("name", code),
        "stance": stance,
        "horizon": "1-4周",
        "summary": summary,
        "actions": actions,
        "levels": {
            "price": price,
            "support": support,
            "resistance": resist,
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
        },
        "path": path,
        "scenarios": scenarios,
        "confidence": round(min(0.85, 0.45 + abs(score - 50) / 100), 2),
        "disclaimer": _disclaimer(),
        "degraded": bool(kline.get("degraded") or sentiment.get("degraded")),
    }


def _actions(stance: str, support: float, resist: float, score: float) -> list[str]:
    common = [
        f"盯住支撑 {support} 与压力 {resist} 的有效突破/跌破",
        "单笔仓位建议分级，避免一次性重仓",
        "重大公告与板块共振时重新评估",
    ]
    if stance in ("逢低关注", "超卖反弹关注"):
        return [
            "回踩支撑附近分批试探，无效跌破则停止加仓",
            f"情绪分 {score:.0f} 偏暖时优先跟随强势结构",
            *common,
        ]
    if stance in ("谨慎减仓", "高位防守"):
        return [
            "反弹至压力区降低仓位，保留观察仓",
            "若放量破位，执行预设止损而非犹豫",
            *common,
        ]
    return [
        "区间操作为主，突破再展开方向性仓位",
        "等待成交量与均线方向一致后再行动",
        *common,
    ]


def _disclaimer() -> str:
    return (
        "本报告由模型基于公开数据自动生成，仅供研究学习，不构成任何投资建议。"
        "股市有风险，决策需独立判断并自担风险。"
    )
