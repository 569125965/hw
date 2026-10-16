from __future__ import annotations

from typing import Any

from app.core.cache import cache
from app.services.forecast import get_forecast
from app.services.fundamental import get_fundamental
from app.services.market import get_kline, get_quote
from app.services.news import get_news
from app.services.sentiment import get_sentiment


def build_research(code: str) -> dict[str, Any]:
    key = f"research:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    quote = get_quote(code)
    kline = get_kline(code, period="day", limit=180)
    fundamental = get_fundamental(code)
    news = get_news(code)
    sentiment = get_sentiment(code)
    forecast = get_forecast(code)

    payload = {
        "code": quote.get("code", code),
        "name": quote.get("name", code),
        "quote": quote,
        "kline": kline,
        "fundamental": fundamental,
        "news": news,
        "sentiment": sentiment,
        "forecast": forecast,
        "degraded": any(
            [
                quote.get("degraded"),
                kline.get("degraded"),
                fundamental.get("degraded"),
                news.get("degraded"),
                sentiment.get("degraded"),
                forecast.get("degraded"),
            ]
        ),
    }
    cache.set(key, payload)
    return payload
