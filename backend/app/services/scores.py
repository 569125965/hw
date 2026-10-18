from __future__ import annotations

from typing import Any

import numpy as np


def build_scorecard(
    *,
    quote: dict[str, Any],
    sentiment: dict[str, Any],
    social: dict[str, Any] | None,
    capital: dict[str, Any] | None,
    macro: dict[str, Any] | None,
    forecast: dict[str, Any] | None,
    advice: dict[str, Any] | None,
) -> dict[str, Any]:
    """多维量化评分（0-100），供蛛网图与批量表格。"""
    social = social or {}
    capital = capital or {}
    macro = macro or {}
    forecast = forecast or {}
    advice = advice or {}
    thesis = capital.get("thesis") or {}
    chips = capital.get("chips") or {}
    vol = capital.get("volume_phase") or {}

    tech = float(sentiment.get("score") or 50)
    heat = float(social.get("heat_score") if social.get("heat_score") is not None else 50)
    polarity = float(social.get("polarity_score") if social.get("polarity_score") is not None else 50)
    mood = float(social.get("mood_score") if social.get("mood_score") is not None else 50)

    # 资金健康：出逃分越高越低
    exit_s = float(thesis.get("exit_score") or 0)
    rally_s = float(thesis.get("rally_score") or 0)
    capital_health = float(np.clip(55 + rally_s * 0.35 - exit_s * 0.55, 5, 95))

    # 筹码安全：相对成本浮盈过大且有负面 → 不安全；贴近成本带更稳
    profit = chips.get("profit_ratio_vs_cost")
    if profit is None:
        chip_safety = 50.0
    else:
        # 适度浮盈加分，过大扣分（派发风险）
        if profit < -10:
            chip_safety = 35.0
        elif profit < 15:
            chip_safety = 70.0 + profit * 0.4
        elif profit < 40:
            chip_safety = 68.0 - (profit - 15) * 0.6
        else:
            chip_safety = 40.0
        if thesis.get("code") in ("capital_exit", "plan_disrupted_watch_exit"):
            chip_safety = min(chip_safety, 42.0)
    chip_safety = float(np.clip(chip_safety, 5, 95))

    # 量能
    vr = float(vol.get("vol_ratio_5_20") or quote.get("volume_ratio") or 1.0)
    volume_energy = float(np.clip(40 + (vr - 1) * 35 + (vol.get("up_volume_days") or 0) * 3, 5, 95))

    # 宏观（风险分越高环境越差）
    risk = float(macro.get("risk_score") or 50)
    macro_env = float(np.clip(100 - risk, 5, 95))

    # 趋势/研判
    stance = str(forecast.get("stance") or "")
    if any(k in stance for k in ("看多", "偏多", "买入", "进攻")):
        trend = 72.0
    elif any(k in stance for k in ("减仓", "防守", "谨慎", "看空")):
        trend = 32.0
    else:
        trend = 50.0
    trend = float(np.clip(0.6 * trend + 0.4 * tech, 5, 95))

    # 消息面：活跃度已在 sentiment，这里用 polarity + news face proxy
    news_quality = float(np.clip(0.55 * polarity + 0.45 * mood, 5, 95))

    # 操作确定性：综合 advice
    combo = float(advice.get("combo_score") or tech)
    action_fit = float(np.clip(combo, 5, 95))

    dims = [
        {"key": "tech", "name": "技术动量", "score": round(tech, 1)},
        {"key": "volume", "name": "量能动能", "score": round(volume_energy, 1)},
        {"key": "heat", "name": "人气热度", "score": round(heat, 1)},
        {"key": "news", "name": "消息质量", "score": round(news_quality, 1)},
        {"key": "capital", "name": "资金健康", "score": round(capital_health, 1)},
        {"key": "chip", "name": "筹码安全", "score": round(chip_safety, 1)},
        {"key": "macro", "name": "宏观环境", "score": round(macro_env, 1)},
        {"key": "trend", "name": "趋势研判", "score": round(trend, 1)},
        {"key": "action", "name": "操作契合", "score": round(action_fit, 1)},
    ]
    overall = float(np.mean([d["score"] for d in dims]))

    # 买卖图标语义
    action_code = advice.get("action_code") or "hold"
    if action_code in ("buy", "watch_buy") and overall >= 58:
        signal = "buy"
        signal_label = "偏多/可关注"
        signal_icon = "▲"
    elif action_code in ("sell", "hold_light") or overall <= 45:
        signal = "sell"
        signal_label = "偏空/减仓"
        signal_icon = "▼"
    else:
        signal = "hold"
        signal_label = "观望"
        signal_icon = "●"

    return {
        "dimensions": dims,
        "overall": round(overall, 1),
        "signal": signal,
        "signal_label": signal_label,
        "signal_icon": signal_icon,
        "action": advice.get("action"),
        "action_code": action_code,
    }


def build_chart_overlays(capital: dict[str, Any] | None, quote: dict[str, Any] | None = None) -> dict[str, Any]:
    """K 线图标注：成本带、历史高位套牢区等。"""
    capital = capital or {}
    chips = capital.get("chips") or {}
    zone = chips.get("cost_zone") or {}
    overlays: list[dict[str, Any]] = []
    if zone.get("low") is not None and zone.get("high") is not None:
        overlays.append(
            {
                "id": "cost_band",
                "type": "band",
                "label": "活动筹码成本带",
                "y0": float(zone["low"]),
                "y1": float(zone["high"]),
                "mid": float(zone.get("mid") or zone["low"]),
                "color": "rgba(232,168,56,0.18)",
                "border": "#e8a838",
            }
        )
    if chips.get("pit_low") is not None:
        overlays.append(
            {
                "id": "pit_low",
                "type": "line",
                "label": "阶段低点",
                "y": float(chips["pit_low"]),
                "color": "#26a69a",
                "style": "dashed",
            }
        )
    if chips.get("hist_high") is not None:
        hi = float(chips["hist_high"])
        # 套牢抛压区：历史高位下 8%~0
        overlays.append(
            {
                "id": "trap_zone",
                "type": "band",
                "label": "高位套牢抛压区",
                "y0": hi * 0.92,
                "y1": hi,
                "mid": hi,
                "color": "rgba(229,57,53,0.12)",
                "border": "#e53935",
            }
        )
        overlays.append(
            {
                "id": "hist_high",
                "type": "line",
                "label": "历史高位/定增压力",
                "y": hi,
                "color": "#e53935",
                "style": "dotted",
            }
        )
    if zone.get("mid") is not None:
        overlays.append(
            {
                "id": "cost_mid",
                "type": "line",
                "label": "筹码成本中枢",
                "y": float(zone["mid"]),
                "color": "#e8a838",
                "style": "solid",
            }
        )
    price = float((quote or {}).get("price") or 0)
    return {
        "overlays": overlays,
        "legend": [
            {"id": o["id"], "label": o["label"], "color": o.get("border") or o.get("color")}
            for o in overlays
            if o["type"] in ("band", "line")
        ],
        "price": price,
    }
