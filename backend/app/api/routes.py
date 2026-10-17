from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.forecast import get_forecast
from app.services.fundamental import get_fundamental
from app.services.market import get_kline, get_quote, search_stocks
from app.services.news import get_news
from app.services.research import STEPS, build_research, events_to_ndjson
from app.services.sentiment import get_sentiment
from app.services.signals import detect_signals
from app.services.social import get_social

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


@router.get("/stocks/{code}/social")
def stocks_social(code: str) -> dict:
    """股吧/新闻舆情、关联热股、关注热度。"""
    return get_social(code)


@router.get("/stocks/{code}/sentiment")
def stocks_sentiment(code: str) -> dict:
    return get_sentiment(code)


@router.get("/stocks/{code}/forecast")
def stocks_forecast(code: str) -> dict:
    return get_forecast(code)


@router.get("/stocks/{code}/research")
def stocks_research(code: str) -> dict:
    return build_research(code)


@router.get("/stocks/{code}/research/stream")
def stocks_research_stream(code: str) -> StreamingResponse:
    """NDJSON 进度流：每行一个步骤事件，最后一步含完整 research。"""
    return StreamingResponse(
        events_to_ndjson(code),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Research-Steps": ",".join(s for s, _ in STEPS),
        },
    )
