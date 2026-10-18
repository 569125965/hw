from __future__ import annotations

from typing import Any


def build_advice(
    *,
    quote: dict[str, Any],
    forecast: dict[str, Any],
    sentiment: dict[str, Any],
    social: dict[str, Any] | None = None,
    capital: dict[str, Any] | None = None,
    macro: dict[str, Any] | None = None,
    llm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """综合技术面 + 舆情 + 筹码资金 + 宏观 +（可选）LLM，给出可执行建议。"""
    price = float(quote.get("price") or 0)
    levels = forecast.get("levels") or {}
    support = float(levels.get("support") or price * 0.95)
    resist = float(levels.get("resistance") or price * 1.05)
    tech_score = float(sentiment.get("score") or 50)
    social_score = float((social or {}).get("mood_score") or tech_score)
    heat_score = (social or {}).get("heat_score")
    stance = str(forecast.get("stance") or "观望整理")
    polarity = (social or {}).get("polarity_score")
    thesis = (capital or {}).get("thesis") or {}
    chips = (capital or {}).get("chips") or {}
    cost_mid = (chips.get("cost_zone") or {}).get("mid")

    if heat_score is not None:
        combo = 0.50 * tech_score + 0.35 * social_score + 0.15 * float(heat_score)
    else:
        combo = 0.55 * tech_score + 0.45 * social_score

    if polarity is not None and float(polarity) <= 42 and heat_score is not None and float(heat_score) >= 80:
        combo = min(combo, 58.0)

    # 资金出逃/派发：压低综合分并倾向减仓
    exitish = thesis.get("code") in (
        "capital_exit",
        "plan_disrupted_watch_exit",
    ) or (thesis.get("exit_score") or 0) >= 55
    if exitish:
        combo = min(combo, 48.0)

    # 宏观避险略降杠杆
    if macro and float(macro.get("risk_score") or 50) >= 70:
        combo = min(combo, combo - 4)

    # LLM 覆盖（若明确给出减仓/回避）
    llm_view = (llm or {}).get("capital_view") or {}
    llm_bias = str(llm_view.get("action_bias") or llm_view.get("capital_behavior") or "")
    if any(k in llm_bias for k in ("减仓", "出逃", "派发", "回避")):
        combo = min(combo, 45.0)
        exitish = True

    if exitish or combo <= 38 or stance in ("谨慎减仓", "高位防守"):
        action = "卖出/减仓"
        action_code = "sell"
        urgency = "逢高减仓·防派发" if exitish else ("逢高减仓" if price >= resist * 0.98 else "控制仓位")
        color = "bearish"
    elif combo >= 68 and price <= resist * 1.02 and not (
        polarity is not None and float(polarity) <= 42
    ):
        action = "买入"
        action_code = "buy"
        urgency = "分批建仓"
        color = "bullish"
    elif abs(combo - 50) < 8 or (
        polarity is not None and float(polarity) <= 42 and heat_score is not None and float(heat_score) >= 80
    ):
        action = "观望"
        action_code = "hold"
        urgency = "高热争议，等待落地" if (polarity is not None and float(polarity) <= 42) else "等待方向选择"
        color = "neutral"
    elif combo > 55:
        action = "逢低关注"
        action_code = "watch_buy"
        urgency = "回踩支撑再试多"
        color = "bullish"
    else:
        action = "谨慎持有"
        action_code = "hold_light"
        urgency = "反弹降低仓位"
        color = "bearish"

    buy_zone = [round(support, 2), round((support + price) / 2, 2)]
    sell_zone = [round((price + resist) / 2, 2), round(resist, 2)]
    stop_loss = round(support * 0.985, 2)
    take_profit = round(resist * 1.01, 2)
    if cost_mid:
        # 筹码成本带作为更贴近实战的参考
        buy_zone = [round(min(buy_zone[0], float(cost_mid) * 0.98), 2), round(min(buy_zone[1], float(cost_mid) * 1.05), 2)]

    reasons = [
        f"技术情绪 {tech_score:.0f} 分，研判「{stance}」",
        f"股吧/新闻舆情 {social_score:.0f} 分（{(social or {}).get('mood_label', '中性')}）",
        f"综合得分 {combo:.0f}，操作倾向「{action}」",
    ]
    if thesis.get("label"):
        reasons.append(
            f"资金研判「{thesis['label']}」（出逃分 {thesis.get('exit_score')} / 拉升分 {thesis.get('rally_score')}，置信 {thesis.get('confidence')}）"
        )
    if cost_mid:
        reasons.append(
            f"估计活动筹码成本约 {cost_mid}（坑后密集区 {chips.get('pit_low')}↑）"
            + (f"，现价相对浮盈 {chips.get('profit_ratio_vs_cost')}%" if chips.get("profit_ratio_vs_cost") is not None else "")
        )
    if capital and capital.get("volume_phase"):
        reasons.append(f"量价阶段：{capital['volume_phase'].get('label')}")
    if social and social.get("hot_rank"):
        heat_lbl = social.get("heat_label") or ""
        reasons.append(
            f"东财人气榜第 {social['hot_rank']}"
            + (f"（关注度{heat_lbl}，热度 {social.get('heat_score')}）" if social.get("heat_score") is not None else "")
        )
    if social and social.get("polarity_score") is not None:
        reasons.append(f"标题倾向 {social['polarity_score']}（热度高也可能偏争议）")
    if macro:
        reasons.append(f"宏观「{macro.get('regime')}」风险分 {macro.get('risk_score')}")
    if llm_view:
        reasons.append(
            f"AI观点：{llm_view.get('capital_behavior') or ''} / {llm_view.get('action_bias') or ''}"
        )

    if action_code in ("buy", "watch_buy"):
        checklist = [
            f"优先在买入参考区 {buy_zone[0]}-{buy_zone[1]} 分 2-3 笔建仓",
            f"跌破止损 {stop_loss} 停止加仓并评估离场",
            f"接近压力 {sell_zone[1]} 降低仓位锁定利润",
            "关注股吧突发利空与公告，出现放量破位立即复核",
        ]
    elif action_code in ("sell", "hold_light"):
        checklist = [
            f"反弹至卖出参考区 {sell_zone[0]}-{sell_zone[1]} 分批减仓",
            f"若放量跌破 {support}，加速降低仓位",
            "对照筹码成本带与主力资金流向，避免在出货浪接盘",
            "负面事件未落地前，不因人气榜回升盲目加仓",
        ]
    else:
        checklist = [
            f"价格落在 {support}-{resist} 区间内以观望为主",
            f"向上有效突破 {resist} 再考虑跟随",
            f"向下有效跌破 {support} 按减仓预案执行",
            "等待股吧/新闻情绪与量价、资金流向一致",
        ]

    return {
        "action": action,
        "action_code": action_code,
        "urgency": urgency,
        "color": color,
        "combo_score": round(combo, 1),
        "tech_score": round(tech_score, 1),
        "social_score": round(social_score, 1),
        "price": price,
        "buy_zone": buy_zone,
        "sell_zone": sell_zone,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "horizon": forecast.get("horizon") or "1-4周",
        "reasons": reasons,
        "checklist": checklist,
        "capital_label": thesis.get("label"),
        "disclaimer": (
            "操作建议由规则引擎综合盘面、筹码、舆情、宏观"
            + ("与大模型" if (llm or {}).get("enabled") else "")
            + "自动生成，仅供研究学习，不构成投资建议。"
        ),
    }
