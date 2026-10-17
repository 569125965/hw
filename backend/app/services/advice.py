from __future__ import annotations

from typing import Any


def build_advice(
    *,
    quote: dict[str, Any],
    forecast: dict[str, Any],
    sentiment: dict[str, Any],
    social: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """综合技术面 + 市场情绪 + 股吧/新闻舆情，给出可执行买卖建议。"""
    price = float(quote.get("price") or 0)
    levels = forecast.get("levels") or {}
    support = float(levels.get("support") or price * 0.95)
    resist = float(levels.get("resistance") or price * 1.05)
    tech_score = float(sentiment.get("score") or 50)
    social_score = float((social or {}).get("mood_score") or tech_score)
    stance = str(forecast.get("stance") or "观望整理")

    # 综合分：技术 55% + 舆情 45%
    combo = 0.55 * tech_score + 0.45 * social_score

    if combo >= 68 and price <= resist * 1.02:
        action = "买入"
        action_code = "buy"
        urgency = "分批建仓"
        color = "bullish"
    elif combo <= 38 or stance in ("谨慎减仓", "高位防守"):
        action = "卖出/减仓"
        action_code = "sell"
        urgency = "逢高减仓" if price >= resist * 0.98 else "控制仓位"
        color = "bearish"
    elif abs(combo - 50) < 8:
        action = "观望"
        action_code = "hold"
        urgency = "等待方向选择"
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

    # 具体价位建议
    buy_zone = [round(support, 2), round((support + price) / 2, 2)]
    sell_zone = [round((price + resist) / 2, 2), round(resist, 2)]
    stop_loss = round(support * 0.985, 2)
    take_profit = round(resist * 1.01, 2)

    reasons = [
        f"技术情绪 {tech_score:.0f} 分，研判「{stance}」",
        f"股吧/新闻舆情 {social_score:.0f} 分（{(social or {}).get('mood_label', '中性')}）",
        f"综合得分 {combo:.0f}，操作倾向「{action}」",
    ]
    if social and social.get("hot_rank"):
        reasons.append(f"东财人气排名约第 {social['hot_rank']}")
    if social and (social.get("guba_count") or 0) > 0:
        bd = social.get("mood_breakdown") or {}
        reasons.append(
            f"股吧近帖利多 {bd.get('positive', 0)} / 利空 {bd.get('negative', 0)}"
        )

    checklist = []
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
            "保留观察仓跟踪舆情与板块联动",
            "避免在情绪极端恐慌时一次性清仓导致踏空反抽",
        ]
    else:
        checklist = [
            f"价格落在 {support}-{resist} 区间内以观望为主",
            f"向上有效突破 {resist} 再考虑跟随",
            f"向下有效跌破 {support} 按减仓预案执行",
            "等待股吧/新闻情绪与量价方向一致",
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
        "disclaimer": (
            "操作建议由模型综合盘面、舆情自动生成，仅供研究学习，不构成投资建议。"
        ),
    }
