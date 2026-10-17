from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator

from app.core.cache import cache
from app.services.advice import build_advice
from app.services.forecast import get_forecast
from app.services.fundamental import get_fundamental
from app.services.market import get_kline, get_quote
from app.services.news import get_news
from app.services.sentiment import get_sentiment
from app.services.social import get_social

STEPS = [
    ("resolve", "识别股票"),
    ("quote", "拉取盘面报价"),
    ("kline", "拉取K线并计算买卖点"),
    ("fundamental", "分析产品与行业"),
    ("news", "聚合官方消息"),
    ("social", "抓取股吧/新闻舆情与关联"),
    ("sentiment", "评估市场情绪"),
    ("forecast", "生成走势研判"),
    ("advice", "给出买卖操作建议"),
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
    yield {"step": "resolve", "status": "running", "label": "识别股票"}

    for step in ("quote", "kline", "fundamental", "news", "social"):
        yield {"step": step, "status": "running", "label": dict(STEPS)[step]}

    quote: dict[str, Any] = {}
    kline: dict[str, Any] = {}
    fundamental: dict[str, Any] = {}
    news: dict[str, Any] = {}
    social: dict[str, Any] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {
            pool.submit(get_quote, code): "quote",
            pool.submit(get_kline, code, "day", 180): "kline",
            pool.submit(get_fundamental, code): "fundamental",
            pool.submit(get_news, code): "news",
            pool.submit(get_social, code): "social",
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
                elif name == "news":
                    news = data
                else:
                    social = data
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

    if not social:
        social = {
            "code": resolved,
            "posts": [],
            "mood_score": 50,
            "mood_label": "中性",
            "related": [],
            "keywords": [],
            "summary": "舆情暂不可用",
            "degraded": True,
        }

    yield {"step": "sentiment", "status": "running", "label": "评估市场情绪"}
    # 情绪计算已纳入人气热度 / 股吧极性；再与舆情综合分轻度对齐
    sentiment = get_sentiment(
        resolved,
        quote=quote,
        kline=kline,
        news=news or {"items": []},
        social=social,
    )
    if social.get("mood_score") is not None:
        blended = round(0.7 * float(sentiment["score"]) + 0.3 * float(social["mood_score"]), 1)
        heat = social.get("heat_score")
        rank = social.get("hot_rank")
        extra = ""
        if rank:
            extra = f"人气榜第 {rank}"
            if heat is not None:
                extra += f"·热度 {heat}"
            extra += "。"
        label = sentiment.get("label") or "中性"
        if heat is not None and float(heat) >= 85:
            label = "高热" if blended >= 55 else "高热观望"
        elif blended >= 65:
            label = "偏多"
        elif blended <= 35:
            label = "偏空"
        sentiment = {
            **sentiment,
            "score": blended,
            "label": label,
            "summary": f"{sentiment.get('summary', '')} 叠加舆情后综合 {blended:.0f} 分。{extra}",
            "social_mood": social.get("mood_score"),
            "heat_score": heat,
            "hot_rank": rank,
        }
    yield {
        "step": "sentiment",
        "status": "done",
        "label": "评估市场情绪",
        "preview": f"{sentiment.get('label')} {sentiment.get('score')}",
    }

    yield {"step": "forecast", "status": "running", "label": "生成走势研判"}
    forecast = get_forecast(resolved, quote=quote, kline=kline, sentiment=sentiment)
    yield {
        "step": "forecast",
        "status": "done",
        "label": "生成走势研判",
        "preview": forecast.get("stance"),
    }

    yield {"step": "advice", "status": "running", "label": "给出买卖操作建议"}
    advice = build_advice(quote=quote, forecast=forecast, sentiment=sentiment, social=social)
    yield {
        "step": "advice",
        "status": "done",
        "label": "给出买卖操作建议",
        "preview": f"{advice.get('action')} · {advice.get('urgency')}",
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

    # enrich peers with social related
    peers = list(fundamental.get("peers") or [])
    seen = {p.get("code") for p in peers}
    for r in social.get("related") or []:
        if r.get("code") in seen:
            continue
        peers.append(
            {
                "code": r["code"],
                "name": r.get("symbol") or r["code"],
                "change_pct": r.get("change_pct"),
                "relation": r.get("relation"),
            }
        )
        seen.add(r["code"])
    fundamental = {**fundamental, "peers": peers}

    payload = {
        "code": resolved,
        "name": quote.get("name", resolved),
        "quote": quote,
        "kline": kline,
        "fundamental": fundamental,
        "news": news,
        "social": social,
        "sentiment": sentiment,
        "forecast": forecast,
        "advice": advice,
        "degraded": any(
            [
                quote.get("degraded"),
                kline.get("degraded"),
                fundamental.get("degraded"),
                news.get("degraded"),
                social.get("degraded"),
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
        return f"{len(data.get('items') or [])} 条官方/资讯"
    if name == "social":
        return (
            f"舆情 {data.get('mood_score')}（{data.get('mood_label')}）· "
            f"股吧 {data.get('guba_count', 0)} · 关联 {len(data.get('related') or [])}"
        )
    return "ok"


def events_to_ndjson(code: str) -> Generator[str, None, None]:
    for event in iter_research_events(code):
        yield json.dumps(event, ensure_ascii=False) + "\n"
