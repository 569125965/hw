from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def llm_status() -> dict[str, Any]:
    configured = bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)
    return {
        "configured": configured,
        "provider": settings.llm_provider,
        "model": settings.llm_model if configured else None,
        "base_url": settings.llm_base_url if configured else None,
        "hint": None
        if configured
        else "在项目根或 backend/.env 配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后启用 AI 深度研判",
    }


def deep_analyze(
    *,
    quote: dict[str, Any],
    capital: dict[str, Any],
    social: dict[str, Any],
    sentiment: dict[str, Any],
    macro: dict[str, Any],
    news: dict[str, Any],
    forecast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调用用户配置的 OpenAI 兼容 API，做筹码/事件/宏观综合研判。"""
    status = llm_status()
    if not status["configured"]:
        return {
            "enabled": False,
            **status,
            "summary": "未配置 LLM，已跳过 AI 深度研判。规则引擎结论见「资金/筹码」。",
            "capital_view": None,
            "raw": None,
        }

    context = {
        "stock": {"code": quote.get("code"), "name": quote.get("name"), "price": quote.get("price"), "change_pct": quote.get("change_pct")},
        "chips": capital.get("chips"),
        "capital_thesis": capital.get("thesis"),
        "volume_phase": capital.get("volume_phase"),
        "money_flow": {
            k: capital.get("money_flow", {}).get(k)
            for k in ("main_net_5d", "main_net_10d", "distribution_up_days", "note", "available")
        },
        "events": capital.get("events"),
        "social": {
            "mood_score": social.get("mood_score"),
            "heat_score": social.get("heat_score"),
            "heat_label": social.get("heat_label"),
            "hot_rank": social.get("hot_rank"),
            "polarity_score": social.get("polarity_score"),
            "summary": social.get("summary"),
        },
        "sentiment": {"score": sentiment.get("score"), "label": sentiment.get("label"), "summary": sentiment.get("summary")},
        "macro": {
            "regime": macro.get("regime"),
            "risk_score": macro.get("risk_score"),
            "summary": macro.get("summary"),
            "headlines": [i.get("title") for i in (macro.get("items") or [])[:12]],
        },
        "news_headlines": [n.get("title") for n in (news.get("items") or [])[:12]],
        "forecast_stance": (forecast or {}).get("stance"),
    }

    system = (
        "你是A股实战研究员。根据给定结构化数据，判断主力/游资行为。"
        "重点：筹码成本带、定增高位、低位建仓、催化、突发负面（如质量门）如何打乱拉升计划，"
        "以及舆论高潮是否构成出货窗口。必须结合美联储/地缘等宏观。"
        "输出严格 JSON，不要 markdown。"
    )
    user = (
        "数据如下（JSON）：\n"
        + json.dumps(context, ensure_ascii=False)
        + "\n请输出 JSON 字段："
        '{"capital_behavior":"出逃|派发|观望|吸筹|拉升","confidence":0-1,'
        '"rationale":"中文推理120-220字","chip_read":"筹码解读",'
        '"event_impact":"负面事件对业绩/计划的影响","macro_overlay":"宏观如何扰动",'
        '"action_bias":"减仓|观望|轻仓试多|回避","risks":["..."],"watchpoints":["..."]}'
    )

    try:
        content = _chat(system, user)
        parsed = _parse_json(content)
        return {
            "enabled": True,
            **status,
            "summary": parsed.get("rationale") or content[:300],
            "capital_view": parsed,
            "raw": content[:4000],
            "degraded": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm deep analyze failed: %s", exc)
        return {
            "enabled": True,
            **status,
            "summary": f"LLM 调用失败：{exc}",
            "capital_view": None,
            "raw": None,
            "degraded": True,
            "error": str(exc),
        }


def _chat(system: str, user: str) -> str:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    with httpx.Client(timeout=60.0) as c:
        r = c.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    return str(data["choices"][0]["message"]["content"])


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        return {"rationale": text[:500]}
