from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.batch import batch_analyze
from app.services.capital import analyze_capital
from app.services.forecast import get_forecast
from app.services.fundamental import get_fundamental
from app.services.llm import llm_status
from app.services.macro import get_macro
from app.services.market import get_kline, get_quote, search_stocks
from app.services.news import get_news
from app.services.research import STEPS, build_research, events_to_ndjson
from app.services.sentiment import get_sentiment
from app.services.signals import detect_signals
from app.services.social import get_social
from app.services import watchlists as wl

router = APIRouter()


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)


class GroupRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)


class StocksAdd(BaseModel):
    stocks: list[dict[str, str]] = Field(default_factory=list)


class BatchBody(BaseModel):
    codes: list[str] = Field(default_factory=list)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ashare-lab", "llm": llm_status()}


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


@router.get("/macro/drivers")
def macro_drivers() -> dict:
    return get_macro()


@router.get("/llm/status")
def llm_config_status() -> dict:
    return llm_status()


@router.get("/stocks/{code}/capital")
def stocks_capital(code: str) -> dict:
    quote = get_quote(code)
    kline = get_kline(code, period="day", limit=360)
    news = get_news(code)
    social = get_social(code)
    return analyze_capital(code, quote=quote, kline=kline, news=news, social=social)


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


@router.get("/watchlists")
def watchlists_list() -> dict:
    return {"groups": wl.list_groups()}


@router.post("/watchlists")
def watchlists_create(body: GroupCreate) -> dict:
    return wl.create_group(body.name)


@router.patch("/watchlists/{group_id}")
def watchlists_rename(group_id: str, body: GroupRename) -> dict:
    try:
        return wl.rename_group(group_id, body.name)
    except KeyError as exc:
        raise HTTPException(404, "分组不存在") from exc


@router.delete("/watchlists/{group_id}")
def watchlists_delete(group_id: str) -> dict:
    try:
        wl.delete_group(group_id)
        return {"ok": True}
    except KeyError as exc:
        raise HTTPException(404, "分组不存在") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/watchlists/{group_id}/stocks")
def watchlists_add_stocks(group_id: str, body: StocksAdd) -> dict:
    try:
        return wl.add_stocks(group_id, body.stocks)
    except KeyError as exc:
        raise HTTPException(404, "分组不存在") from exc


@router.delete("/watchlists/{group_id}/stocks/{code}")
def watchlists_remove_stock(group_id: str, code: str) -> dict:
    try:
        return wl.remove_stock(group_id, code)
    except KeyError as exc:
        raise HTTPException(404, "分组不存在") from exc


@router.post("/research/batch")
def research_batch(body: BatchBody) -> dict[str, Any]:
    codes = body.codes[:30]
    if not codes:
        raise HTTPException(400, "请至少选择一只股票")
    return batch_analyze(codes)
