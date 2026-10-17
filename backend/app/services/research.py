from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator

from app.core.cache import cache
from app.services.forecast import get_forecast
from app.services.fundamental import get_fundamental
from app.services.market import get_kline, get_quote
from app.services.news import get_news
from app.services.sentiment import get_sentiment

STEPS = [
    ("resolve", "识别股票"),
    ("quote", "拉取盘面报价"),
    ("kline", "拉取K线并计算买卖点"),
    ("fundamental", "分析产品与行业"),
    ("news", "聚合消息面"),
    ("sentiment", "评估市场情绪"),
    ("forecast", "生成操作思路与预测"),
    ("done", "研究完成"),
]


def build_research(code: str) -> dict[str, Any]:
    key = f"research:{code}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    payload = None
    for event in iter_research_events(code):
        if event.get("step") == "done" and event.get("status") == "done":
            payload = event.get("research")
    if payload is None:
        raise RuntimeError("research failed")
    cache.set(key, payload)
    return payload


def iter_research_events(code: str) -> Generator[dict[str, Any], None, None]:
    """Yield progress events; final event carries full research payload."""
    yield {"step": "resolve", "status": "running", "label": "识别股票"}

    # parallel fetch independent slices
    yield {"step": "quote", "status": "running", "label": "拉取盘面报价"}
    yield {"step": "kline", "status": "running", "label": "拉取K线并计算买卖点"}
    yield {"step": "fundamental", "status": "running", "label": "分析产品与行业"}
    yield {"step": "news", "status": "running", "label": "聚合消息面"}

    quote: dict[str, Any] = {}
    kline: dict[str, Any] = {}
    fundamental: dict[str, Any] = {}
    news: dict[str, Any] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {
            pool.submit(get_quote, code): "quote",
            pool.submit(get_kline, code, "day", 180): "kline",
            pool.submit(get_fundamental, code): "fundamental",
            pool.submit(get_news, code): "news",
        }
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                data = fut.result()
                if name == "quote":
                    quote = data
                elif name == "kline":
                    kline = data
                elif name == "fundamental":
                    fundamental = data
                else:
                    news = data
                yield {
                    "step": name,
                    "status": "done",
                    "label": dict(STEPS)[name],
                    "preview": _preview(name, data),
                }
            except Exception as exc:  # noqa: BLE001
                errors[name] = str(exc)
                yield {
                    "step": name,
                    "status": "error",
                    "label": dict(STEPS)[name],
                    "error": str(exc),
                }

    if not quote or not kline:
        yield {
            "step": "done",
            "status": "error",
            "label": "研究失败",
            "error": "盘面或K线拉取失败：" + "; ".join(f"{k}={v}" for k, v in errors.items()),
        }
        return

    resolved = quote.get("code", code)
    yield {
        "step": "resolve",
        "status": "done",
        "label": "识别股票",
        "preview": f"{quote.get('name')} ({resolved})",
    }

    yield {"step": "sentiment", "status": "running", "label": "评估市场情绪"}
    sentiment = get_sentiment(resolved, quote=quote, kline=kline, news=news or {"items": []})
    yield {
        "step": "sentiment",
        "status": "done",
        "label": "评估市场情绪",
        "preview": f"{sentiment.get('label')} {sentiment.get('score')}",
    }

    yield {"step": "forecast", "status": "running", "label": "生成操作思路与预测"}
    forecast = get_forecast(resolved, quote=quote, kline=kline, sentiment=sentiment)
    yield {
        "step": "forecast",
        "status": "done",
        "label": "生成操作思路与预测",
        "preview": forecast.get("stance"),
    }

    if not fundamental:
        fundamental = {
            "code": resolved,
            "name": quote.get("name", resolved),
            "industry": "未知",
            "concepts": [],
            "products": [],
            "business_summary": "基本面暂时不可用",
            "peers": [],
            "degraded": True,
        }
    if not news:
        news = {"code": resolved, "name": quote.get("name", resolved), "items": [], "degraded": True}

    payload = {
        "code": resolved,
        "name": quote.get("name", resolved),
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
        "errors": errors or None,
    }
    cache.set(f"research:{resolved}", payload)
    if resolved != code:
        cache.set(f"research:{code}", payload)

    yield {"step": "done", "status": "done", "label": "研究完成", "research": payload}


def _preview(name: str, data: dict[str, Any]) -> str:
    if name == "quote":
        return f"{data.get('name')} {data.get('price')} ({data.get('change_pct')}%)"
    if name == "kline":
        n = len(data.get("items") or [])
        s = len(data.get("signals") or [])
        return f"{n} 根K线 · {s} 个买卖点"
    if name == "fundamental":
        return f"{data.get('industry')} · {len(data.get('concepts') or [])} 个概念"
    if name == "news":
        return f"{len(data.get('items') or [])} 条消息"
    return "ok"


def events_to_ndjson(code: str) -> Generator[str, None, None]:
    for event in iter_research_events(code):
        yield json.dumps(event, ensure_ascii=False) + "\n"
