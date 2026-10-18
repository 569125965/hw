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
    social: dict[str, Any] | None = None,
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

    items = news.get("items") or []
    news_count = len(items)
    pos = sum(1 for n in items if n.get("sentiment") == "positive")
    neg = sum(1 for n in items if n.get("sentiment") == "negative")
    news_polarity = 50.0
    if pos + neg > 0:
        news_polarity = 50 + (pos - neg) / (pos + neg) * 30
    # 消息活跃度：条数多≠冷清；铺天盖地时应抬升「消息面」分量
    news_activity = float(np.clip(40 + news_count * 4, 40, 95))
    news_score = 0.55 * news_polarity + 0.45 * news_activity

    tech = 50.0
    tech += np.clip(ret_5 * 100, -12, 12)
    tech += np.clip(ret_20 * 60, -10, 10)
    tech += np.clip((vol_ratio - 1) * 10, -8, 8)
    tech += np.clip((rsi - 50) / 5, -8, 8)
    tech += np.clip(macd / max(abs(close.iloc[-1]) * 0.01, 0.01), -6, 6)

    heat = None
    hot_rank = None
    polarity_social = None
    if social:
        if social.get("heat_score") is not None:
            heat = float(social["heat_score"])
        hot_rank = social.get("hot_rank")
        if social.get("polarity_score") is not None:
            polarity_social = float(social["polarity_score"])
        # 股吧/新闻帖并入活跃度
        social_posts = int(social.get("guba_count") or 0) + int(social.get("news_count") or 0)
        if social_posts > 0:
            news_activity = float(np.clip(max(news_activity, 45 + social_posts * 1.2), 40, 98))
            news_score = 0.55 * news_polarity + 0.45 * news_activity

    # 市场情绪 = 技术动量 + 消息极性/活跃 + 人气热度
    if heat is not None:
        score = 0.40 * tech + 0.25 * news_score + 0.35 * heat
    else:
        score = 0.65 * tech + 0.35 * news_score
    if polarity_social is not None and heat is not None:
        # 轻微纳入股吧标题倾向，避免只看热度忽视利空争议
        score = 0.85 * score + 0.15 * polarity_social
    score = float(np.clip(score, 0, 100))

    if heat is not None and heat >= 85:
        label = "高热" if score >= 55 else "高热观望"
    elif score >= 65:
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
        {"name": "消息倾向", "value": round(news_polarity, 1), "impact": _impact((news_polarity - 50) / 50)},
        {"name": "消息活跃", "value": round(news_activity, 1), "impact": _impact((news_activity - 50) / 50)},
    ]
    if heat is not None:
        factors.append(
            {
                "name": "人气热度",
                "value": round(heat, 1),
                "impact": _impact((heat - 50) / 50),
            }
        )
    if hot_rank:
        factors.append(
            {
                "name": "东财人气排名",
                "value": float(hot_rank),
                "impact": "positive" if hot_rank <= 50 else "neutral" if hot_rank <= 200 else "negative",
            }
        )

    heat_phrase = ""
    if hot_rank:
        heat_phrase = f"东财人气榜第 {hot_rank}，"
    elif heat is not None:
        heat_phrase = f"人气热度 {heat:.0f}，"

    if news_activity >= 75 or (heat is not None and heat >= 80):
        news_face = "铺天盖地/高度关注"
    elif news_activity >= 55:
        news_face = "活跃"
    elif news_polarity >= 55:
        news_face = "偏暖"
    elif news_polarity <= 45:
        news_face = "偏冷"
    else:
        news_face = "中性"

    polarity_note = ""
    if polarity_social is not None and polarity_social <= 42:
        polarity_note = "标题偏争议/利空，热度≠看多。"
    elif polarity_social is not None and polarity_social >= 58:
        polarity_note = "标题偏利多。"

    summary = (
        f"{quote.get('name', code)} 综合情绪得分 {score:.0f}（{label}）。"
        f"{heat_phrase}"
        f"短线动量{'偏强' if ret_5 > 0 else '偏弱'}，"
        f"量能{'放大' if vol_ratio > 1.1 else '平稳' if vol_ratio > 0.9 else '收缩'}，"
        f"消息面{news_face}。"
        f"{polarity_note}"
    )

    return {
        "code": code,
        "name": quote.get("name", code),
        "score": round(score, 1),
        "label": label,
        "factors": factors,
        "summary": summary,
        "heat_score": round(heat, 1) if heat is not None else None,
        "hot_rank": hot_rank,
        "degraded": bool(kline.get("degraded") or news.get("degraded")),
    }


def _impact(v: float) -> str:
    if v > 0.02:
        return "positive"
    if v < -0.02:
        return "negative"
    return "neutral"
