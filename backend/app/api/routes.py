from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.forecast import get_forecast
from app.services.fundamental import get_fundamental
from app.services.market import get_kline, get_quote, search_stocks
from app.services.news import get_news
from app.services.research import build_research
from app.services.sentiment import get_sentiment
from app.services.signals import detect_signals

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ashare-lab"}


@router.get("/stocks/search")
def stocks_search(q: str = Query("", max_length=32)) -> dict:
    return {"items": search_stocks(q)}


@router.get("/stocks/{code}/quote")
def stocks_quote(code: str) -> dict:
    return get_quote(code)


@router.get("/stocks/{code}/kline")
def stocks_kline(
    code: str,
    period: str = Query("day", pattern="^(day|week)$"),
    limit: int = Query(180, ge=30, le=500),
) -> dict:
    return get_kline(code, period=period, limit=limit)


@router.get("/stocks/{code}/signals")
def stocks_signals(
    code: str,
    period: str = Query("day", pattern="^(day|week)$"),
    limit: int = Query(180, ge=30, le=500),
) -> dict:
    kline = get_kline(code, period=period, limit=limit)
    return {
        "code": kline["code"],
        "period": period,
        "signals": kline.get("signals") or detect_signals(kline["items"]),
        "definitions": {
            "short": "短期约5-20个交易日：MA5/MA10+RSI+放量，买卖成对",
            "medium": "中期约20-60个交易日：MA20/MA60+MACD+布林，买卖成对",
        },
    }


@router.get("/stocks/{code}/fundamental")
def stocks_fundamental(code: str) -> dict:
    return get_fundamental(code)


@router.get("/stocks/{code}/news")
def stocks_news(code: str, limit: int = Query(20, ge=1, le=50)) -> dict:
    return get_news(code, limit=limit)


@router.get("/stocks/{code}/sentiment")
def stocks_sentiment(code: str) -> dict:
    return get_sentiment(code)


@router.get("/stocks/{code}/forecast")
def stocks_forecast(code: str) -> dict:
    return get_forecast(code)


@router.get("/stocks/{code}/research")
def stocks_research(code: str) -> dict:
    return build_research(code)
