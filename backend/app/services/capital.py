from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np

from app.providers import flow as flow_provider
from app.services.indicators import kline_to_df

logger = logging.getLogger(__name__)

EVENT_PATTERNS: list[tuple[str, str, str]] = [
    ("private_placement", "定增/增发", r"定增|定向增发|增发|非公开发行"),
    ("coop", "合作催化", r"玛莎拉蒂|Maserati|华为|尊界|合作|战略|合资"),
    ("delivery", "交付催化", r"交付|量产|上市发布|大定"),
    ("scandal", "负面冲击", r"刹车|调查|召回|下架|断裂|争议|踩断|质量门"),
    ("earnings", "业绩", r"业绩|净利|营收|预告|亏损|扭亏"),
]


def analyze_capital(
    code: str,
    *,
    quote: dict[str, Any],
    kline: dict[str, Any],
    news: dict[str, Any] | None = None,
    social: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """筹码成本估计 + 资金行为研判（吸筹/拉升/派发/出逃）。"""
    code = code.zfill(6)
    df = kline_to_df(kline.get("items") or [])
    news_items = list((news or {}).get("items") or [])
    social = social or {}
    price = float(quote.get("price") or (df["close"].iloc[-1] if not df.empty else 0))

    chips = _estimate_chips(df, price)
    events = _extract_events(news_items, social.get("posts") or [])
    volume_phase = _volume_phase(df)
    money = _money_flow_summary(code, df)

    thesis = _judge_thesis(
        price=price,
        chips=chips,
        events=events,
        volume_phase=volume_phase,
        money=money,
        social=social,
    )

    return {
        "code": code,
        "name": quote.get("name", code),
        "price": price,
        "chips": chips,
        "events": events,
        "volume_phase": volume_phase,
        "money_flow": money,
        "thesis": thesis,
        "summary": thesis.get("summary", ""),
        "degraded": bool(df.empty),
    }


def _estimate_chips(df, price: float) -> dict[str, Any]:
    if df is None or df.empty or len(df) < 30:
        return {
            "vwap_60": None,
            "vwap_120": None,
            "pit_low": None,
            "pit_date": None,
            "cost_zone": None,
            "placement_hint": None,
            "profit_ratio_vs_cost": None,
            "note": "K线不足，无法估计筹码",
        }

    close = df["close"].astype(float)
    low = df["low"].astype(float)
    high = df["high"].astype(float)
    vol = df["volume"].astype(float).clip(lower=1)
    amount = df["amount"].astype(float) if "amount" in df.columns else close * vol

    def vwap(n: int) -> float:
        sub = df.tail(n)
        a = sub["amount"].astype(float) if "amount" in sub.columns else sub["close"].astype(float) * sub["volume"].astype(float)
        v = sub["volume"].astype(float).clip(lower=1)
        return float(a.sum() / v.sum())

    vwap_60 = vwap(min(60, len(df)))
    vwap_120 = vwap(min(120, len(df)))

    # 挖坑：近 1-2 年最低区域 + 随后放量横盘的成交密集
    pit_idx = int(low.idxmin()) if hasattr(low, "idxmin") else int(np.argmin(low.values))
    # use positional
    pit_pos = int(np.argmin(low.values))
    pit_low = float(low.iloc[pit_pos])
    pit_date = str(df.iloc[pit_pos]["date"]) if "date" in df.columns else ""

    # 坑后 40 根K的量价成本 ≈ 机构/游资主要建仓带
    after = df.iloc[pit_pos : pit_pos + 45]
    if len(after) >= 8:
        a = after["amount"].astype(float) if "amount" in after.columns else after["close"].astype(float) * after["volume"].astype(float)
        v = after["volume"].astype(float).clip(lower=1)
        cost_mid = float(a.sum() / v.sum())
        cost_lo = float(after["low"].astype(float).quantile(0.2))
        cost_hi = float(after["high"].astype(float).quantile(0.7))
    else:
        cost_mid = pit_low * 1.08
        cost_lo = pit_low
        cost_hi = pit_low * 1.2

    # 历史高位区：可能对应定增/解禁压力（用户提到 ~49.8）
    hi_pos = int(np.argmax(high.values))
    hist_high = float(high.iloc[hi_pos])
    hist_high_date = str(df.iloc[hi_pos]["date"]) if "date" in df.columns else ""
    placement_hint = None
    if hist_high >= cost_mid * 1.8:
        placement_hint = {
            "ref_high": round(hist_high, 2),
            "ref_date": hist_high_date,
            "note": f"历史高位约 {hist_high:.2f}，若附近有过定增/增发，高位筹码套牢压力大，低位{cost_mid:.1f}附近更可能是主流活动筹码",
        }

    profit = (price / cost_mid - 1.0) if cost_mid else None

    return {
        "vwap_60": round(vwap_60, 2),
        "vwap_120": round(vwap_120, 2),
        "pit_low": round(pit_low, 2),
        "pit_date": pit_date,
        "cost_zone": {
            "low": round(cost_lo, 2),
            "mid": round(cost_mid, 2),
            "high": round(cost_hi, 2),
        },
        "hist_high": round(hist_high, 2),
        "hist_high_date": hist_high_date,
        "placement_hint": placement_hint,
        "profit_ratio_vs_cost": round(profit * 100, 2) if profit is not None else None,
        "note": (
            f"低点约 {pit_low:.2f}（{pit_date}），坑后成交密集成本约 {cost_mid:.2f}"
            f"（{cost_lo:.2f}-{cost_hi:.2f}）；现价相对该成本"
            f"{'浮盈' if profit and profit > 0 else '浮亏'} "
            f"{abs(profit*100):.1f}%" if profit is not None else ""
        ),
    }


def _extract_events(news_items: list[dict], posts: list[dict]) -> list[dict[str, Any]]:
    pool = []
    for n in news_items:
        pool.append(("news", n.get("title") or "", n.get("published_at") or "", n.get("summary") or ""))
    for p in posts[:40]:
        pool.append(("social", p.get("title") or "", p.get("published_at") or "", p.get("summary") or ""))

    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src, title, ts, summary in pool:
        text = f"{title} {summary}"
        is_scandal_ctx = bool(re.search(r"刹车|调查|召回|下架|断裂|争议|踩断|质量门", text))
        for key, label, pat in EVENT_PATTERNS:
            if not re.search(pat, text, re.I):
                continue
            # 负面语境中的「尊界/华为」不算利好催化
            if key in ("coop", "delivery") and is_scandal_ctx:
                continue
            sig = f"{key}:{title[:40]}"
            if sig in seen:
                continue
            seen.add(sig)
            found.append(
                {
                    "type": key,
                    "label": label,
                    "title": title[:120],
                    "published_at": ts,
                    "source": src,
                    "bearish": key == "scandal",
                }
            )
    # prioritize scandals and catalysts
    order = {"scandal": 0, "private_placement": 1, "coop": 2, "delivery": 3, "earnings": 4}
    found.sort(key=lambda x: order.get(x["type"], 9))
    return found[:20]


def _volume_phase(df) -> dict[str, Any]:
    if df is None or df.empty or len(df) < 25:
        return {"label": "未知", "up_volume_days": 0, "vol_ratio_5_20": None}

    close = df["close"].astype(float)
    vol = df["volume"].astype(float)
    ret = close.pct_change().fillna(0)
    vol_ma20 = vol.rolling(20).mean()
    recent = df.tail(12)
    up_vol = 0
    for i in range(len(recent)):
        row = recent.iloc[i]
        idx = recent.index[i]
        # align with full series
        pos = df.index.get_loc(idx)
        if pos == 0:
            continue
        if float(close.iloc[pos]) > float(close.iloc[pos - 1]) and float(vol.iloc[pos]) > float(vol_ma20.iloc[pos] or vol.iloc[pos]):
            up_vol += 1

    vr = float(vol.tail(5).mean() / max(float(vol.tail(20).mean()), 1))
    last_5_ret = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0.0

    if up_vol >= 5 and vr >= 1.3 and last_5_ret > 0:
        label = "连续放量拉升"
    elif up_vol >= 3 and vr >= 1.15:
        label = "放量活跃"
    elif last_5_ret < -0.05 and vr >= 1.2:
        label = "放量下跌"
    elif vr < 0.85:
        label = "缩量"
    else:
        label = "常态波动"

    return {
        "label": label,
        "up_volume_days": up_vol,
        "vol_ratio_5_20": round(vr, 2),
        "ret_5d": round(last_5_ret * 100, 2),
    }


def _money_flow_summary(code: str, df) -> dict[str, Any]:
    try:
        rows = flow_provider.fetch_money_flow(code, limit=60)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money flow failed: %s", exc)
        return {"available": False, "error": str(exc)}

    if not rows:
        return {"available": False}

    main = [r["main_net"] for r in rows]
    recent5 = main[-5:]
    recent10 = main[-10:]
    # 上涨日主力净流出 = 派发特征
    dist_days = 0
    if df is not None and not df.empty:
        by_date = {str(r["date"])[:10]: r for r in rows}
        for _, row in df.tail(15).iterrows():
            d = str(row["date"])[:10]
            fr = by_date.get(d)
            if not fr:
                continue
            prev_i = df.index.get_loc(row.name)
            if prev_i == 0:
                continue
            up = float(row["close"]) > float(df.iloc[prev_i - 1]["close"])
            if up and fr["main_net"] < 0:
                dist_days += 1

    return {
        "available": True,
        "main_net_5d": round(sum(recent5), 2),
        "main_net_10d": round(sum(recent10), 2),
        "main_net_today": round(main[-1], 2) if main else None,
        "distribution_up_days": dist_days,
        "series_tail": rows[-8:],
        "note": (
            f"近5日主力净流入 {sum(recent5)/1e8:.2f} 亿，近10日 {sum(recent10)/1e8:.2f} 亿；"
            f"近15日「上涨且主力流出」{dist_days} 天"
        ),
    }


def _judge_thesis(
    *,
    price: float,
    chips: dict[str, Any],
    events: list[dict[str, Any]],
    volume_phase: dict[str, Any],
    money: dict[str, Any],
    social: dict[str, Any],
) -> dict[str, Any]:
    cost = (chips.get("cost_zone") or {}).get("mid")
    profit_pct = chips.get("profit_ratio_vs_cost")
    scandals = [e for e in events if e.get("type") == "scandal"]
    catalysts = [e for e in events if e.get("type") in ("coop", "delivery")]
    placements = [e for e in events if e.get("type") == "private_placement"]

    heat = social.get("heat_score")
    polarity = social.get("polarity_score")
    hot_rank = social.get("hot_rank")

    signals: list[str] = []
    score_exit = 0  # 出逃/派发嫌疑分
    score_rally = 0

    if cost and profit_pct is not None and profit_pct >= 15:
        signals.append(f"现价相对坑后成本带（约 {cost}）已有约 {profit_pct:.0f}% 空间，具备兑现利润条件")
        score_exit += 18
    if cost and profit_pct is not None and profit_pct >= 40:
        score_exit += 10

    if volume_phase.get("label") == "连续放量拉升":
        signals.append("数据面呈现连续放量拉升，符合主力拉升或诱多派发前的量价形态")
        score_rally += 15
        score_exit += 8  # 拉升后更容易进入派发窗口

    if catalysts:
        signals.append("存在合作/交付类催化：" + "；".join(e["title"][:40] for e in catalysts[:2]))
        score_rally += 12

    if scandals:
        signals.append("突发负面冲击：" + "；".join(e["title"][:40] for e in scandals[:2]))
        signals.append("负面冲击会打乱原有拉升计划：业绩受损概率显著高于「完全无影响」")
        score_exit += 28
        score_rally -= 10

    if placements:
        signals.append("公告/舆情提及定增增发，需对照历史高位与低位筹码结构")
        score_exit += 5

    if chips.get("placement_hint"):
        signals.append(chips["placement_hint"]["note"])

    # 高热 + 标题偏空 + 舆论反弹叙事 → 派发给散户
    if heat is not None and float(heat) >= 80 and polarity is not None and float(polarity) <= 45:
        signals.append(
            f"人气极高（热度 {heat}"
            + (f"·榜第 {hot_rank}" if hot_rank else "")
            + f"）但标题倾向偏空（{polarity}），符合「争议中拉升/诱多」的散户接盘结构"
        )
        score_exit += 22

    if money.get("available"):
        signals.append(money.get("note") or "")
        if (money.get("main_net_5d") or 0) < 0:
            score_exit += 14
            signals.append("近5日主力资金净流出，偏流出/减仓")
        elif (money.get("main_net_5d") or 0) > 0 and not scandals:
            score_rally += 10
        if (money.get("distribution_up_days") or 0) >= 3:
            score_exit += 16
            signals.append("多次「上涨日主力净流出」，经典派发特征")

    # 归一
    score_exit = int(np.clip(score_exit, 0, 100))
    score_rally = int(np.clip(score_rally, 0, 100))

    if score_exit >= 55 and score_exit > score_rally + 8:
        code = "capital_exit"
        label = "资本出逃/派发嫌疑"
        confidence = min(0.88, 0.45 + score_exit / 200)
        direction = "bearish_distribution"
    elif score_rally >= 50 and score_rally > score_exit + 5 and not scandals:
        code = "capital_accumulate_rally"
        label = "资金拉升/做多延续"
        confidence = min(0.82, 0.42 + score_rally / 200)
        direction = "bullish"
    elif scandals and score_exit >= 40:
        code = "plan_disrupted_watch_exit"
        label = "拉升计划被负面打乱，警惕出货"
        confidence = min(0.8, 0.4 + score_exit / 220)
        direction = "cautious"
    else:
        code = "inconclusive"
        label = "资金行为尚不明确"
        confidence = 0.35
        direction = "neutral"

    scenarios = [
        {
            "name": "负面冲击伤及业绩/品牌",
            "probability": 0.62 if scandals else 0.25,
            "desc": "调查/质量事件持续发酵，订单与估值双杀，高位与舆论反弹成为出货窗口。",
        },
        {
            "name": "事件可控、催化回归",
            "probability": 0.22 if scandals else 0.45,
            "desc": "官方澄清或影响有限，合作/交付主线重启，但需放量站稳成本带上方。",
        },
        {
            "name": "高位震荡消耗人气",
            "probability": 0.16 if scandals else 0.3,
            "desc": "多空分歧加大，游资与机构轮换，等待宏观与资金流向定调。",
        },
    ]

    summary = (
        f"资金研判「{label}」（置信约 {confidence:.0%}）。"
        + (f"估计活动筹码成本约 {cost} 元；" if cost else "")
        + f"量价阶段：{volume_phase.get('label')}。"
        + ("负面冲击下「完全无业绩影响」概率很低，舆论拉升更需防派发。" if scandals else "")
    )

    return {
        "code": code,
        "label": label,
        "direction": direction,
        "confidence": round(confidence, 2),
        "exit_score": score_exit,
        "rally_score": score_rally,
        "signals": [s for s in signals if s],
        "scenarios": scenarios,
        "summary": summary,
        "needs_llm": code == "inconclusive" or confidence < 0.55,
    }
