from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.services.advice import build_advice
from app.services.capital import analyze_capital
from app.services.forecast import get_forecast
from app.services.macro import get_macro
from app.services.market import get_kline, get_quote
from app.services.news import get_news
from app.services.scores import build_chart_overlays, build_scorecard
from app.services.sentiment import get_sentiment
from app.services.social import get_social

logger = logging.getLogger(__name__)


def analyze_one(code: str, *, macro: dict[str, Any] | None = None) -> dict[str, Any]:
    """轻量单票分析，用于批量表格。"""
    code = code.zfill(6)
    quote = get_quote(code)
    kline = get_kline(code, period="day", limit=180)
    kline_long = get_kline(code, period="day", limit=360)
    news = get_news(code, limit=12)
    social = get_social(code)
    macro = macro or get_macro()
    capital = analyze_capital(code, quote=quote, kline=kline_long, news=news, social=social)
    sentiment = get_sentiment(code, quote=quote, kline=kline, news=news, social=social)
    if social.get("mood_score") is not None:
        blended = round(0.7 * float(sentiment["score"]) + 0.3 * float(social["mood_score"]), 1)
        sentiment = {**sentiment, "score": blended}
    forecast = get_forecast(code, quote=quote, kline=kline, sentiment=sentiment)
    advice = build_advice(
        quote=quote,
        forecast=forecast,
        sentiment=sentiment,
        social=social,
        capital=capital,
        macro=macro,
        llm={"enabled": False},
    )
    scorecard = build_scorecard(
        quote=quote,
        sentiment=sentiment,
        social=social,
        capital=capital,
        macro=macro,
        forecast=forecast,
        advice=advice,
    )
    overlays = build_chart_overlays(capital, quote)
    thesis = capital.get("thesis") or {}
    return {
        "code": quote.get("code", code),
        "name": quote.get("name", code),
        "price": quote.get("price"),
        "change_pct": quote.get("change_pct"),
        "overall": scorecard["overall"],
        "signal": scorecard["signal"],
        "signal_icon": scorecard["signal_icon"],
        "signal_label": scorecard["signal_label"],
        "action": advice.get("action"),
        "action_code": advice.get("action_code"),
        "urgency": advice.get("urgency"),
        "summary": (
            f"{thesis.get('label') or advice.get('action')}；"
            f"{(capital.get('summary') or sentiment.get('summary') or '')[:80]}"
        ),
        "capital_label": thesis.get("label"),
        "hot_rank": social.get("hot_rank"),
        "heat_score": social.get("heat_score"),
        "scorecard": scorecard,
        "chart_overlays": overlays,
        "dimensions": scorecard["dimensions"],
    }


def batch_analyze(codes: list[str], max_workers: int = 4) -> dict[str, Any]:
    uniq: list[str] = []
    seen: set[str] = set()
    for c in codes:
        c = str(c).zfill(6)
        if c.isdigit() and c not in seen:
            uniq.append(c)
            seen.add(c)
    if not uniq:
        return {"items": [], "count": 0}

    macro = get_macro()
    items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(uniq))) as pool:
        futs = {pool.submit(analyze_one, c, macro=macro): c for c in uniq}
        for fut in as_completed(futs):
            code = futs[fut]
            try:
                items.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                logger.warning("batch %s failed: %s", code, exc)
                errors[code] = str(exc)
                items.append(
                    {
                        "code": code,
                        "name": code,
                        "overall": 0,
                        "signal": "hold",
                        "signal_icon": "!",
                        "signal_label": "失败",
                        "action": "—",
                        "summary": f"分析失败：{exc}",
                        "error": str(exc),
                    }
                )
    items.sort(key=lambda x: float(x.get("overall") or 0), reverse=True)
    return {"items": items, "count": len(items), "errors": errors or None}
