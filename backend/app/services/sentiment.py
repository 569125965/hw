from __future__ import annotations

from typing import Any

import numpy as np

from app.services.indicators import add_indicators, kline_to_df
from app.services.market import get_kline, get_quote
from app.services.news import get_news


def get_sentiment(
    code: str,
    *,
    quote: dict[str, Any] | None = None,
    kline: dict[str, Any] | None = None,
    news: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quote = quote or get_quote(code)
    kline = kline or get_kline(code, period="day", limit=180)
    news = news or get_news(code, limit=12)

    df = add_indicators(kline_to_df(kline["items"]))
    if df.empty:
        return {
            "code": code,
            "name": quote.get("name", code),
            "score": 50,
            "label": "中性",
            "factors": [],
            "summary": "数据不足，情绪中性。",
        }

    close = df["close"]
    ret_5 = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0.0
    ret_20 = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0.0
    vol = df["volume"].astype(float)
    vol_ratio = float(vol.iloc[-5:].mean() / max(vol.iloc[-20:].mean(), 1))
    rsi = float(df["rsi"].dropna().iloc[-1]) if df["rsi"].notna().any() else 50.0
    macd = float(df["macd"].dropna().iloc[-1]) if df["macd"].notna().any() else 0.0

    news_score = 50.0
    pos = sum(1 for n in news["items"] if n.get("sentiment") == "positive")
    neg = sum(1 for n in news["items"] if n.get("sentiment") == "negative")
    if pos + neg > 0:
        news_score = 50 + (pos - neg) / (pos + neg) * 30

    score = 50.0
    score += np.clip(ret_5 * 100, -12, 12)
    score += np.clip(ret_20 * 60, -10, 10)
    score += np.clip((vol_ratio - 1) * 10, -8, 8)
    score += np.clip((rsi - 50) / 5, -8, 8)
    score += np.clip(macd / max(abs(close.iloc[-1]) * 0.01, 0.01), -6, 6)
    score = 0.7 * score + 0.3 * news_score
    score = float(np.clip(score, 0, 100))

    if score >= 65:
        label = "偏多"
    elif score <= 35:
        label = "偏空"
    else:
        label = "中性"

    factors = [
        {"name": "近5日涨跌", "value": round(ret_5 * 100, 2), "impact": _impact(ret_5)},
        {"name": "近20日涨跌", "value": round(ret_20 * 100, 2), "impact": _impact(ret_20)},
        {"name": "量能比", "value": round(vol_ratio, 2), "impact": _impact(vol_ratio - 1)},
        {"name": "RSI", "value": round(rsi, 1), "impact": _impact((rsi - 50) / 50)},
        {"name": "MACD", "value": round(macd, 3), "impact": _impact(macd)},
        {"name": "消息情绪", "value": round(news_score, 1), "impact": _impact((news_score - 50) / 50)},
    ]

    summary = (
        f"{quote.get('name', code)} 综合情绪得分 {score:.0f}（{label}）。"
        f"短线动量{'偏强' if ret_5 > 0 else '偏弱'}，"
        f"量能{'放大' if vol_ratio > 1.1 else '平稳' if vol_ratio > 0.9 else '收缩'}，"
        f"消息面{'偏暖' if news_score >= 55 else '偏冷' if news_score <= 45 else '中性'}。"
    )

    return {
        "code": code,
        "name": quote.get("name", code),
        "score": round(score, 1),
        "label": label,
        "factors": factors,
        "summary": summary,
        "degraded": bool(kline.get("degraded") or news.get("degraded")),
    }


def _impact(v: float) -> str:
    if v > 0.02:
        return "positive"
    if v < -0.02:
        return "negative"
    return "neutral"
